# Registro de mantenimiento — S.V.D.D. School

Curso: Evolución y Mantenimiento de Software (2026-II)
Proyecto base: [rushgala27/School-Management-System](https://github.com/rushgala27/School-Management-System) (Python + Tkinter + SQLite, licencia MIT) — etiqueta `v1.0`.

Clasificación del mantenimiento **basada en la intención** (ISO/IEC 14764):

| Tipo | Intención |
|---|---|
| Correctivo | Reparar un defecto que ya produce fallas observables. |
| Preventivo | Eliminar un defecto latente antes de que se convierta en falla. |
| Adaptativo | Mantener el software utilizable ante cambios de su entorno. |
| Perfectivo | Añadir capacidades o mejorar usabilidad/rendimiento sin que exista falla. |

---

## Versión 2.0 — etiqueta `v2.0`

### R01 — Validación de campos numéricos

- **Descripción:** Mobile No. y Aadhaar Card No. aceptaban letras y caracteres inválidos. Deben restringirse a solo dígitos (10 y 12) y mostrar un mensaje claro cuando el dato no es válido.
- **Prioridad:** Alta
- **Tipo de mantenimiento:** Preventivo — el dato inválido se guardaba sin error, pero dejaba registros corruptos que fallarían al usarse.
- **Commit:** `118b102`
- **Observaciones (problemas durante la modificación):**
  - El `validatecommand` de Tk evalúa el texto completo propuesto: al **pegar** un número con guiones (`8829-3250-8844`, el formato que ya había en la base) se rechazaba entero y el campo quedaba vacío. Hubo que interceptar `<<Paste>>` y limpiar los separadores antes de insertar.
  - La base ya tenía datos que no pasaban la validación: todos los Aadhaar con guiones y registros de prueba con letras (usuarios `2222`, `6666`, `3` y `5555`, este último duplicado). Se escribió una migración idempotente: quita guiones y deja en `NULL` los valores imposibles de recuperar.
  - El director tenía **dos celulares en un solo campo** (`2345671234/4657382910`); la migración conserva el primero.
  - Al probar la edición apareció un defecto previo: *Edit Teacher/Student Info* mapeaba "Aadhaar Card No." a la columna `ano`, que no existe (`OperationalError: no such column: ano`). Se corrigió a `adno`.
- **Evidencia:** ![R01](capturas/v2/r01_validacion_mensaje.png)

### R02 — Navegación estable entre paneles

- **Descripción:** Al pasar entre *Add New Teacher*, *Edit Personal Info* y *Edit Teacher Info* se abrían ventanas duplicadas y la anterior no siempre se cerraba bien. El botón *Back* debe volver al panel correcto sin perder la sesión.
- **Prioridad:** Alta
- **Tipo de mantenimiento:** Correctivo — falla reproducible: cada clic abría otra ventana y se podía abrir un segundo panel de sesión desde el login.
- **Commit:** `56b2485`
- **Observaciones:**
  - Cada `Toplevel` volvía a llamar a `mainloop()`: había **8 bucles de eventos anidados** y cada ventana abierta apilaba uno más. Se dejó un solo `mainloop()` en la ventana raíz.
  - El login seguía visible durante la sesión, así que se podían abrir paneles dobles. Al ocultarlo, cerrar el panel con la **X** dejaba el proceso vivo sin ninguna ventana visible; hubo que asignar `WM_DELETE_WINDOW` para que la X haga lo mismo que *Back* (cerrar sesión y volver al login).
  - Con un usuario inexistente el login mostraba el error y luego se caía con `TypeError: 'NoneType' object is not subscriptable`.
  - En las pruebas, `winfo_exists()` lanzaba `TclError` al consultar una ventana de un intérprete Tk ya destruido (en lugar de devolver `False`); se protegió el registro de ventanas.
- **Evidencia:** usuario inexistente sin excepción y vuelta al login limpio tras *Back*:
  ![R02 usuario inexistente](capturas/v2/r02_usuario_inexistente.png)
  ![R02 vuelta al login](capturas/v2/r02_vuelta_al_login.png)

### R03 — Carga y vista previa de foto

- **Descripción:** El campo Photo solo guardaba un texto de referencia (`PHOTO11`), no la imagen. Se implementa selector de archivo con miniatura y validación del formato antes de guardar.
- **Prioridad:** Media
- **Tipo de mantenimiento:** Perfectivo — capacidad nueva; no corrige una falla existente.
- **Commit:** `bb1a307`
- **Observaciones:**
  - Las tablas no tenían dónde guardar la imagen. `ALTER TABLE ... ADD COLUMN photo_blob BLOB` conserva los registros, pero **rompió todos los `INSERT ... VALUES` posicionales** (`table TeacherData has 20 columns but 19 values were supplied`). Se reescribieron con columnas explícitas y parámetros `?`; de paso, los apellidos con apóstrofo (`D'Souza`) ya no rompen el SQL.
  - Tk no lee JPG de forma nativa: se agregó Pillow (`requirements.txt`).
  - La extensión no basta: un `.txt` renombrado a `.png` pasaba el filtro del selector. Se valida el contenido con `Image.verify()`, el formato y un máximo de 2 MB.
  - La miniatura aparecía en blanco si el `PhotoImage` solo vivía en una variable local (Python lo libera); se guarda la referencia en el propio `Label`.
- **Evidencia:** archivo falso rechazado, miniatura en el alta y foto en el panel del docente:
  ![R03 archivo no válido](capturas/v2/r03_archivo_no_valido.png)
  ![R03 miniatura](capturas/v2/r03_formulario_con_miniatura.png)
  ![R03 panel con foto](capturas/v2/r03_panel_docente_con_foto.png)

---

## Versión 3.0 — etiqueta `v3.0`

Sin cambios de código: se agrega el campo **Tipo de mantenimiento** a cada requerimiento de la v2.0 (clasificación basada en la intención, arriba) y este registro al repositorio.

| Req. | Título | Tipo de mantenimiento |
|---|---|---|
| R01 | Validación de campos numéricos | Preventivo |
| R02 | Navegación estable entre paneles | Correctivo |
| R03 | Carga y vista previa de foto | Perfectivo |
