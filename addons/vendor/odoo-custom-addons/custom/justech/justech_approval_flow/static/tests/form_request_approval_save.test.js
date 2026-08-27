/** @odoo-module **/
import { describe, expect, test } from "@odoo/hoot";
import { click, edit, queryAll, queryOne } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels, fields, makeServerError, models, mountView, onRpc } from "@web/../tests/web_test_helpers";
import "@justech_approval_flow/js/form_request_approval_save";

defineMailModels();

class AccountMove extends models.Model {
    _name = "account.move";

    name = fields.Char();
    state = fields.Char({ default: "draft" });
    partner_id = fields.Many2one({ relation: "res.partner", required: true });
    quantity = fields.Float({ default: 1 });
    justech_approval_state = fields.Char({ default: "none" });
    justech_approval_invoice_enabled = fields.Boolean({ default: true });

    _records = [
        {
            id: 1,
            name: "INV-UAT-DIRTY",
            state: "draft",
            partner_id: 17,
            quantity: 1,
            justech_approval_state: "none",
            justech_approval_invoice_enabled: true,
        },
    ];

    _views = {
        form: /* xml */ `
            <form>
                <header>
                    <button name="action_justech_request_approval"
                            type="object"
                            string="Solicitar aprobación"
                            class="btn-primary o_justech_request_approval"/>
                </header>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="partner_id"/>
                        <field name="quantity"/>
                        <field name="justech_approval_state"/>
                    </group>
                </sheet>
            </form>
        `,
    };
}

defineModels({ AccountMove });

describe("justech_approval_flow.request_save", () => {
    test.timeout(20000);
    test("Solicitar aprobación button is in the form header", async () => {
        await mountView({ type: "form", resModel: "account.move", resId: 1 });
        expect(".o_justech_request_approval").toHaveCount(1);
        expect(queryOne(".o_justech_request_approval")).toHaveText("Solicitar aprobación");
    });

    test("dirty quantity is saved before request RPC", async () => {
        onRpc("web_save", ({ args, kwargs }) => {
            expect.step("save");
            const vals = (args && args[1]) || kwargs.vals || {};
            expect(vals.quantity).toBe(3);
        });
        onRpc("action_justech_request_approval", () => {
            expect.step("request");
            return true;
        });
        await mountView({ type: "form", resModel: "account.move", resId: 1 });
        await click("div[name='quantity'] input");
        await edit("3", { confirm: false });
        await click(".o_justech_request_approval");
        await animationFrame();
        expect.verifySteps(["save", "request"]);
    });

    test("required failure does not call request RPC", async () => {
        onRpc("web_save", () => {
            expect.step("save");
        });
        onRpc("action_justech_request_approval", () => {
            expect.step("request");
            return true;
        });
        await mountView({ type: "form", resModel: "account.move" });
        await click(".o_justech_request_approval");
        await animationFrame();
        expect.verifySteps([]);
        expect(queryAll(".o_notification_manager .o_notification").length).toBeGreaterThan(0);
    });

    test("debounce / double click does not duplicate request RPC", async () => {
        const gate = new Deferred();
        let saves = 0;
        let requests = 0;
        onRpc("web_save", async () => {
            saves += 1;
            await gate;
        });
        onRpc("action_justech_request_approval", () => {
            requests += 1;
            return true;
        });
        await mountView({ type: "form", resModel: "account.move", resId: 1 });
        await click("div[name='quantity'] input");
        await edit("4", { confirm: false });
        click(".o_justech_request_approval");
        click(".o_justech_request_approval");
        await animationFrame();
        gate.resolve();
        await animationFrame();
        expect(saves).toBe(1);
        expect(requests).toBe(1);
    });

    test("RPC success after save", async () => {
        onRpc("web_save", () => {
            expect.step("save");
        });
        onRpc("action_justech_request_approval", () => {
            expect.step("request-ok");
            return true;
        });
        await mountView({ type: "form", resModel: "account.move", resId: 1 });
        await click("div[name='quantity'] input");
        await edit("2", { confirm: false });
        await click(".o_justech_request_approval");
        await animationFrame();
        expect.verifySteps(["save", "request-ok"]);
    });

    test("save RPC failure shows notification and does not request", async () => {
        expect.errors(1);
        onRpc("web_save", () => {
            throw makeServerError();
        });
        onRpc("action_justech_request_approval", () => {
            expect.step("request");
            return true;
        });
        await mountView({ type: "form", resModel: "account.move", resId: 1 });
        await click("div[name='quantity'] input");
        await edit("5", { confirm: false });
        await click(".o_justech_request_approval");
        await animationFrame();
        expect.verifyErrors(["RPC_ERROR: Odoo Server Error"]);
        expect.verifySteps([]);
        expect(queryAll(".o_notification_manager .o_notification").length).toBeGreaterThan(0);
    });
});
