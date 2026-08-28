# -*- coding: utf-8 -*-

from uuid import uuid4

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestCompanyRuleUniqueness(JustechApprovalCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env["justech.approval.user.rule"]
        cls.Company = cls.env["res.company"]
        cls.company_alt = cls.Company.create({"name": "ALT-APPROVAL-%s" % uuid4().hex[:6]})

        cls.user_multi = cls.env["res.users"].create(
            {
                "name": "Multi Company Approver",
                "login": "multi_%s" % uuid4().hex[:8],
                "email": "multi.rule@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, (cls.company | cls.company_alt).ids)],
            }
        )
        cls.user_alt = cls.env["res.users"].create(
            {
                "name": "Alt Company Approver",
                "login": "alt_%s" % uuid4().hex[:8],
                "email": "alt.rule@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                "company_id": cls.company_alt.id,
                "company_ids": [(6, 0, cls.company_alt.ids)],
            }
        )

    def test_company_column_visible_in_list_view(self):
        view = self.env.ref("justech_approval_flow.view_justech_approval_user_rule_list")
        self.assertIn('name="company_id"', view.arch_db)

    def test_company_is_required(self):
        field = self.Rule._fields["company_id"]
        self.assertTrue(field.required)

    def test_same_user_different_company_allowed(self):
        self.Rule.create(
            {
                "user_id": self.user_multi.id,
                "company_id": self.company.id,
                "approve_sale": True,
            }
        )
        self.Rule.create(
            {
                "user_id": self.user_multi.id,
                "company_id": self.company_alt.id,
                "approve_purchase": True,
            }
        )
        rows = self.Rule.search([("user_id", "=", self.user_multi.id)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped("company_id.id")), {self.company.id, self.company_alt.id})

    def test_same_user_same_company_duplicate_blocked(self):
        self.Rule.create(
            {
                "user_id": self.user_alt.id,
                "company_id": self.company_alt.id,
                "approve_sale": True,
            }
        )
        with self.assertRaises(Exception):
            self.Rule.create(
                {
                    "user_id": self.user_alt.id,
                    "company_id": self.company_alt.id,
                    "approve_invoice": True,
                }
            )

    def test_routing_scoped_by_company(self):
        self.Rule.create(
            {
                "user_id": self.user_multi.id,
                "company_id": self.company.id,
                "approve_sale": True,
            }
        )
        self.Rule.create(
            {
                "user_id": self.user_alt.id,
                "company_id": self.company_alt.id,
                "approve_sale": True,
            }
        )

        users_main = self.Rule.approvers_for_type("sale_order", company=self.company)
        users_alt = self.Rule.approvers_for_type("sale_order", company=self.company_alt)

        self.assertIn(self.user_multi, users_main)
        self.assertNotIn(self.user_alt, users_main)
        self.assertIn(self.user_alt, users_alt)
        self.assertNotIn(self.user_multi, users_alt)

    def _drop_unique(self):
        self.env.cr.execute(
            """
            SELECT conname
              FROM pg_constraint
             WHERE conrelid = 'justech_approval_user_rule'::regclass
               AND contype = 'u'
               AND pg_get_constraintdef(oid) ILIKE '%%UNIQUE (user_id, company_id)%%'
            """
        )
        row = self.env.cr.fetchone()
        if row:
            self.env.cr.execute(
                'ALTER TABLE justech_approval_user_rule DROP CONSTRAINT "%s"' % row[0]
            )

    def _restore_unique(self):
        self.env.cr.execute(
            """
            SELECT count(*)
              FROM pg_constraint
             WHERE conrelid = 'justech_approval_user_rule'::regclass
               AND contype = 'u'
               AND pg_get_constraintdef(oid) ILIKE '%%UNIQUE (user_id, company_id)%%'
            """
        )
        if not self.env.cr.fetchone()[0]:
            self.env.cr.execute(
                """
                ALTER TABLE justech_approval_user_rule
                ADD CONSTRAINT justech_approval_user_rule_user_company_uniq
                UNIQUE (user_id, company_id)
                """
            )

    def test_migration_normalizes_exact_duplicates(self):
        base = self.Rule.create(
            {
                "user_id": self.user_alt.id,
                "company_id": self.company_alt.id,
                "approve_sale": True,
            }
        )
        self._drop_unique()
        self.env.cr.execute(
            """
            INSERT INTO justech_approval_user_rule
                (user_id, company_id, active, approve_sale, approve_purchase, approve_invoice, allow_self_approval, create_uid, write_uid, create_date, write_date)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now()),
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            """,
            (
                base.user_id.id,
                base.company_id.id,
                base.active,
                base.approve_sale,
                base.approve_purchase,
                base.approve_invoice,
                base.allow_self_approval,
                self.env.user.id,
                self.env.user.id,
                base.user_id.id,
                base.company_id.id,
                base.active,
                base.approve_sale,
                base.approve_purchase,
                base.approve_invoice,
                base.allow_self_approval,
                self.env.user.id,
                self.env.user.id,
            ),
        )
        self.env["justech.approval.user.rule"].normalize_company_rules(strict_conflict=True)
        self._restore_unique()
        rows = self.Rule.with_context(active_test=False).search(
            [("user_id", "=", base.user_id.id), ("company_id", "=", base.company_id.id)]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.id, base.id)

    def test_migration_rejects_conflicting_duplicates(self):
        base = self.Rule.create(
            {
                "user_id": self.user_alt.id,
                "company_id": self.company_alt.id,
                "approve_sale": True,
                "approve_purchase": False,
                "approve_invoice": False,
            }
        )
        self._drop_unique()
        self.env.cr.execute(
            """
            INSERT INTO justech_approval_user_rule
                (user_id, company_id, active, approve_sale, approve_purchase, approve_invoice, allow_self_approval, create_uid, write_uid, create_date, write_date)
            VALUES
                (%s, %s, true, false, true, false, false, %s, %s, now(), now())
            """,
            (base.user_id.id, base.company_id.id, self.env.user.id, self.env.user.id),
        )
        with self.assertRaises(ValidationError):
            self.env["justech.approval.user.rule"].normalize_company_rules(
                strict_conflict=True
            )
        self.env.cr.execute(
            """
            DELETE FROM justech_approval_user_rule
             WHERE id IN (
                 SELECT id
                   FROM justech_approval_user_rule
                  WHERE user_id = %s
                    AND company_id = %s
                  ORDER BY id DESC
                  LIMIT 1
             )
            """,
            (base.user_id.id, base.company_id.id),
        )
        self._restore_unique()
