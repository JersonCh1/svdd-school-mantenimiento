# Dónde retomar

Estado al **26-09-2026**: versión **v4.1** publicada (interfaz en español). Las tareas del curso v2.0, v3.0 y v4.0 están implementadas, etiquetadas y con release.

- Repositorio: https://github.com/JersonCh1/svdd-school-mantenimiento (remoto `origin`; `upstream` = proyecto original de rushgala27).
- Carpeta local: `D:\Proyectos\mis-proyectos\svdd-school-mantenimiento`.
- Registro de cada cambio (descripción, prioridad, tipo de mantenimiento, observaciones reales y capturas): [docs/MANTENIMIENTO.md](docs/MANTENIMIENTO.md).
- Capturas que se entregaron en la Ev01 (búsqueda del proyecto): `docs/capturas/ev01/`.

## Comandos

```bash
pip install -r requirements.txt           # Pillow
python SchoolManagementSystem.py          # abrir la app
python -m unittest -v                     # 37 pruebas
python herramientas/verificar_app.py      # recorrido real de la interfaz con los 3 roles (Windows)
```

Generar el `.exe` (requiere `pip install pyinstaller`):

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name SVDD-School --add-data "testdata.db;." SchoolManagementSystem.py
# queda en dist/SVDD-School.exe
```

## Cómo hacer la próxima versión (v5.0 u otra tarea)

1. Leer la consigna y ver cómo la resolvieron los compañeros en la hoja compartida.
2. Definir los requerimientos nuevos (R01–R03) sin repetir los anteriores. Hay candidatos abajo.
3. **Un commit por requerimiento**, con mensajes `v5.0 R01: ...`. Antes de cada commit:
   `python -m unittest` y `python herramientas/verificar_app.py`. Si se cambian textos de botones, actualizar ese script.
4. Anotar en `docs/MANTENIMIENTO.md` los problemas **reales** que aparezcan al programar: son las "Observaciones" de la hoja.
5. `git tag -a v5.0 -m "..."`, luego `git push origin main --tags`, y crear el release:
   `gh release create v5.0 <exe> --repo JersonCh1/svdd-school-mantenimiento --verify-tag --latest --title ... --notes ...`
   (siempre con `--repo`: sin él, `gh` apunta al repositorio original).
6. Llenar la pestaña JERSON de la hoja con los mismos textos.

## Requerimientos candidatos (problemas reales que siguen en el código)

- **Contraseñas en texto plano** en la base: guardarlas con hash (`hashlib.scrypt` o `pbkdf2_hmac` + sal) y migrar las existentes. *Preventivo.*
- **Usuarios duplicados**: existen dos registros `5555` en TeacherData y nada impide crear otro igual. Índice único sobre `username` + validación en el alta. *Correctivo.*
- **Campos obligatorios**: el alta permite guardar un docente o alumno sin nombre, usuario ni contraseña. *Correctivo.*
- **Cambiar la foto** de un usuario ya existente: hoy solo se puede elegir en el alta. *Perfectivo.*
- **Edición por nombre + número de registro escritos a mano**: elegir a la persona desde una lista para evitar errores de tipeo. *Perfectivo.*
- **Búsqueda y listado** de alumnos y docentes (hoy no hay forma de verlos todos). *Perfectivo.*
- **Fechas como texto libre** ("24/07/1968"): validar el formato o usar un selector. *Preventivo.*
- **Respaldo de la base** desde la app (copiar testdata.db con fecha). *Preventivo.*

## Trampas conocidas

- Tk ignora eventos como `<<Paste>>` en ventanas no visibles: en las pruebas no usar `root.withdraw()`.
- Con PyInstaller `--onefile`, `__file__` apunta a una carpeta temporal: por eso `db.ruta_por_defecto()` usa la carpeta del `.exe`.
- En modo WAL aparecen `testdata.db-wal` y `-shm` mientras la app está abierta (ignorados por Git); al cerrar se vuelcan a `testdata.db`.
- Las capturas de verificación se toman por ventana (PrintWindow). Nunca copiar la pantalla ni simular el teclado del sistema.
