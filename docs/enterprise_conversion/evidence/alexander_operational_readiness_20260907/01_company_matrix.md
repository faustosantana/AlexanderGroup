# 01 — Matriz operativa por empresa

Fuente: Excel Levantamiento + prod `doralex_prod` 2026-09-07 (`op_ready_verify.json`).
No se inventaron campos.

STATUS: READY | PARTIAL | MISSING | BLOCKED | NOT_APPLICABLE | NEEDS_BUSINESS_CONFIRMATION

| COMPANY | AREA | ITEM | CURRENT_VALUE | EXPECTED_VALUE | SOURCE | STATUS | ACTION_REQUIRED | RISK |
|---|---|---|---|---|---|---|---|---|
| DORALEX | LEGAL | razón social | INVERSIONES DORALEX,S.RL. | igual | Excel/Odoo | READY | none | LOW |
| DORALEX | LEGAL | RNC | 132220112 | 1-32-22011-2 | Excel | READY | none | LOW |
| DORALEX | LEGAL | state_id | Santo Domingo | SANTO DOMINGO | Excel → fix 2026-09-07 | READY | none | LOW |
| DORALEX | LEGAL | fecha inicio | 2020-11-02 | 2020-11-02 | Excel → l10n_do_dgii_start_date | READY | none | LOW |
| DORALEX | LEGAL | representante + cédula | Alexander Piña Aquino / 223-0157134-9 | igual | Excel | READY | none | LOW |
| DORALEX | LEGAL | correo | administracion@inversionesdoralex.com | Excel personal inversionesdoralex@gmail.com | Odoo UX vs Excel | NEEDS_BUSINESS_CONFIRMATION | no sobrescribir; confirmar From | MEDIUM |
| DORALEX | ACC | diarios venta/compra + ITBIS 18 | Ventas · DOR / Compras · DOR / 18% ITBIS | >=1 | Odoo l10n_do | READY | no rehacer plan de cuentas | LOW |
| DORALEX | BANK | Banreservas | 9604436830 ligado a diario | 9604436830 / 5,000,000 | Excel | PARTIAL | no postear saldo; fecha Excel inválida | HIGH |
| DORALEX | AR | apertura | 16491966.46 | lote 27 facturas | opening import | READY | no modificar históricos | LOW |
| DORALEX | AP | apertura | 0 | Excel CxP=0 | Excel | READY | flujo futuro listo | LOW |
| DORALEX | NCF | B15 | next B1500000152 active auth 6005109381 | B1500000152 | histórico+rango | READY | no consumir en QA | LOW |
| DORALEX | NCF | B01 | next B0100000054 active auth 6005372487 | B0100000054 | histórico+rango 52-87 | READY | históricos 35-51 fuera de rango; no inventar auth | MEDIUM |
| DORALEX | NCF | B13 | BLOCKED max B1300000016 > rango …0015 | confirmar DGII | planilla+CxC | BLOCKED | no inventar 0017 ni rango | HIGH |
| DORALEX | INV | almacén | Almacén Principal | Oficina principal | Excel/Odoo | READY | no inventar existencias | LOW |
| DORALEX | INV | stock apertura | no hay stock real; QA DX-TEST-STK=-23 | PENDING_BUSINESS_DATA | prod quants | NEEDS_BUSINESS_CONFIRMATION | no fusionar/borrar a ciegas | HIGH |
| DORALEX | USERS | Alexander multiempresa | login activo, default Doralex, companies 8-13 | 1 usuario no 6 | Excel Usuarios | READY | no duplicar usuarios | LOW |
| DORALEX | REPORTS | identidad SO staging | RNC 1-32-22011-2 + banco 9604436830 | identidad propia | QWeb 58 | READY | logo header débil | MEDIUM |
| PIÑARIA | LEGAL | RNC/state/inicio/rep | 132271068 / Santo Domingo / 2021-03-01 / Alba Rafaelina Arias Mora 280-103907-0 | Excel | Excel+fix | READY | none | LOW |
| PIÑARIA | BANK | Banreservas | 9604097492 / GL posted 0.00 | 2,450,000 | Excel | PARTIAL | no postear hasta fecha válida | HIGH |
| PIÑARIA | AR | apertura | 0.00 | 0 (sin CxC en lote) | opening | READY | none | LOW |
| PIÑARIA | NCF | rango real | 0 SAFE_ACTIVE | evidencia DGII | planilla insuficiente | BLOCKED | no activar B15 planilla 93-103 | HIGH |
| PIÑARIA | ACC | diarios+ITBIS+WH | Ventas · PIN / Compras · PIN / Almacén Principal | operar | Odoo | READY | none | LOW |
| DOMINION | LEGAL | RNC/state/inicio/rep | 132721502 / Distrito Nacional / 2022-11-09 / Arisleydi Contreras Suero 402-4200332-1 | Excel | Excel+fix | READY | none | LOW |
| DOMINION | BANK | Banreservas | 9605588726 / posted 0.00 | 1,500,000 (Ahorros) | Excel | PARTIAL | no postear; tipo Ahorros no tipificado extra | HIGH |
| DOMINION | NCF | rango real | 0 SAFE_ACTIVE | evidencia DGII | — | BLOCKED | no inventar autorización | HIGH |
| MAYUMA | LEGAL | RNC/state/inicio/rep | 132710152 / Santo Domingo / 2022-09-14 / Eldris Marlenny Ramirez Minaya 402-4218015-2 | Excel | Excel+fix | READY | none | LOW |
| MAYUMA | BANK | Banreservas | 9605543104 / posted 0.00 | 3,000,000 | Excel | PARTIAL | no postear | HIGH |
| MAYUMA | AR | apertura | 2668855.73 | lote | opening | READY | none | LOW |
| MAYUMA | NCF | B15 | next B1500000111 active auth 5004942280 range 109-118 | B1500000111 | histórico 110 | READY | no activar otros tipos | LOW |
| REMPART | LEGAL | RNC/state/inicio/rep | 132769155 / Santo Domingo / 2023-01-19 / Agustin Ventura Alcantara 402-2314668-5 | Excel | Excel+fix | READY | none | LOW |
| REMPART | BANK | Banreservas | 9608739498 / posted 0.00 | 4,600,000 | Excel | PARTIAL | no postear | HIGH |
| REMPART | AR | apertura | 8079389.61 | lote | opening | READY | B1500000110 = 267250.52 no tocar | LOW |
| REMPART | NCF | B15 | next B1500000111 active auth 5004942351 range 106-113 | B1500000111 | histórico 110 | READY | none | LOW |
| BLUE ELITE | LEGAL | RNC/state/inicio/rep | 133371261 / Santo Domingo / 2025-04-04 / Geilin Rosario Suero 402-1097505-4 | Excel | Excel+fix | READY | none | LOW |
| BLUE ELITE | BANK | Banreservas | 9608670542 / posted 0.00 | 1,250,000 | Excel | PARTIAL | no postear | HIGH |
| BLUE ELITE | NCF | rango real | 0 SAFE_ACTIVE | evidencia DGII | planilla 101/102 vs rango 1-20 | BLOCKED | no activar | HIGH |
| ALL6 | TECH | company_id=1 | Plantilla técnica USD/US | no operativa | Odoo | NOT_APPLICABLE | no archivar aún | MEDIUM |
| ALL6 | CROSS | record rules | foreign=0 con usuario restringido | 0 leaks | prod test | READY | none | LOW |
| ALL6 | MAIL | SMTP | 0 ir.mail_server | envío por empresa | Odoo | MISSING | no enviar QA; falta servidor | HIGH |
| ALL6 | ECF | operacional | False | OFF | ir.config_parameter | READY | no activar | LOW |
