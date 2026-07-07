# Scripts manuales

Estos ficheros son **scripts de prueba manual** (basados en `print`), no tests
automatizados de pytest. Se ejecutaban a mano durante el desarrollo para
inspeccionar el flujo de onboarding, a veces con Playwright contra el frontend
desplegado.

Se conservan como referencia pero **no** los recoge la suite de pytest
(`testpaths = tests` en `pytest.ini`). Los tests reales viven en `../tests/`.

Para ejecutarlos manualmente:

```bash
cd apps/backend
python3 scripts/manual/test_onboarding.py
```
