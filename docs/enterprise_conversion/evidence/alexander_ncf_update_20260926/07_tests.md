# 07 — Tests

Suite local `tests/test_ncf_b15_update.py`:

- `test_doralex_b15_range`
- `test_doralex_b15_next_152`
- `test_mayuma_b15_range`
- `test_mayuma_b15_next_113`
- `test_rempart_b15_range`
- `test_rempart_b15_next_112`
- `test_doralex_b13_blocked`
- `test_ncf_next_not_consumed_on_read`
- `test_ncf_low_balance_warning`
- `test_cross_company_authorized_sequences_are_isolated`
- `test_manifest_has_balance_view_and_version`

QA runtime (staging + prod): preview ORM sin consumo; verify PASS;
fingerprint de rangos no objetivo = 0 cambios.

`python3 -m pytest`: 244 passed / 0 failed (incluye los 11 tests B15).

Black de los archivos nuevos: PASS. `make lint` del repo completo falla por
árboles vendor preexistentes, no por este cambio.

No se posteó documento QA. No se envió DGII / e-CF / email.
