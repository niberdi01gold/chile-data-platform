# Incidente: el IPC dejó de actualizarse en la fuente

| | |
|---|---|
| **Fecha de detección** | 2026-10-16 |
| **Severidad** | Media: un indicador de nueve sin datos recientes |
| **Estado** | Abierto: mitigación pendiente |
| **Detectado por** | Prueba automática de frescura (`src/calidad.py`) |

## Qué pasó

La prueba `datos al día (frescura)` falló para el IPC: el último dato disponible es de
**diciembre de 2025** (319 días de antigüedad), cuando el máximo aceptado es 75 días.

## Investigación

1. Se revisó la capa silver: el IPC termina en `2025-12-01`.
2. Se revisó la capa bronze: el archivo histórico de 2026 viene con `serie` vacía (0 registros).
3. Se consultó la fuente directamente (`https://mindicador.cl/api/ipc`): el dato más reciente
   también es `2025-12-01`.

## Causa

La fuente **mindicador.cl dejó de publicar el IPC** después de diciembre de 2025.
El pipeline funciona correctamente; el problema está en el origen de los datos.

## Por qué no se detectó antes

El extractor solo validaba que la respuesta tuviera la forma correcta, no que trajera datos
recientes. Una respuesta vacía era técnicamente válida.

## Acciones

- [x] Agregar pruebas de frescura por indicador, con umbrales según su calendario de publicación.
- [x] Mantener la prueba fallando mientras el problema siga abierto, para que no se olvide.
- [ ] Agregar una fuente alternativa oficial para el IPC (API del Banco Central de Chile o INE).
- [ ] Alertar automáticamente cuando una prueba falle (fase de orquestación).

## Lección

Una respuesta sin errores no significa datos correctos. Validar la forma de los datos no
basta: también hay que validar que estén completos y al día.