# ecommerce-etl

ETL con arquitectura medallion (Bronze / Silver / Gold) para un dataset de e-commerce
brasileño. Ingesta seis CSVs crudos con errores inyectados (nulos, duplicados, valores
fuera de rango, formatos inconsistentes e integridad referencial rota), los limpia,
produce tablas analíticas y genera reportes de calidad en cada etapa.

## Cómo ejecutar

Solo necesitas Docker:

```
docker compose up --build
```

Construye la imagen, corre el pipeline completo y escribe los resultados en `./data/`
(montado como volumen). Al terminar tendrás:

- `data/bronze/`, `data/silver/`, `data/gold/`: parquets por capa.
- `data/quarantine/`: filas descartadas, cada una con su razón.
- `data/quality/`: reportes de calidad.
- `data/warehouse.duckdb`: base DuckDB con todo lo anterior, para consultar por SQL.

### Desarrollo local (opcional)

El proyecto se gestiona con uv. La imagen de Docker no depende de uv: instala con pip
desde `requirements.txt`, que se genera del lock con `make requirements`.

```
uv sync --extra dev     # dependencias
uv run etl              # correr el pipeline
uv run pytest -q        # tests
```

## Flujo de datos

```
data/raw/*.csv
  -> Bronze   ingesta tal cual + metadata (_source_file, _ingested_at)  -> data/bronze/*.parquet
  -> Silver   limpieza por tabla; rechazos -> quarantine; métricas -> quality
  -> Gold     tablas analíticas a partir de Silver                      -> data/gold/*.parquet
  -> Serve    carga en DuckDB, un schema por capa                       -> data/warehouse.duckdb
```

Bronze solo preserva, Silver corrige, Gold agrega. Silver se procesa en orden de
dependencia (customers y products antes que orders; orders antes que order_items,
payments y reviews) porque los checks de integridad referencial leen el Silver ya
limpio del padre.

## Estructura

```
src/ecommerce_etl/
  config.py       rutas y constantes (sin lógica)
  enums.py        valores permitidos por columna (categorías, status, tipos de pago)
  io.py           lectura/escritura (CSV crudo, Parquet)
  transforms.py   transformaciones puras y reutilizables (DataFrame -> DataFrame)
  quality.py      QualityReport: acumula checks en formato largo
  schemas.py      contratos Pandera, uno por tabla Silver
  bronze.py       ingesta genérica raw -> bronze
  silver.py       limpieza por tabla bronze -> silver (+ quarantine, quality, gate)
  gold.py         tablas analíticas
  serve.py        carga a DuckDB
  pipeline.py     orquestación (entrypoint `etl`)
tests/            pytest sobre transforms y quality
notebook.ipynb    recorrido interactivo de la limpieza
```

## Decisiones de diseño

### Tecnologías

- Polars para el procesamiento. A este volumen (~71k filas) el rendimiento no es el
  factor decisivo; se eligió por su API de expresiones y su manejo explícito de nulos y
  tipos, que hace la limpieza más directa y evita conversiones implícitas.
- Pandera como contrato de cada tabla Silver. Valida forma y tipos y lanza excepción si
  algo no cuadra, sirviendo de red ante un bug de limpieza.
- DuckDB como capa de servicio. Deja las tablas consultables por SQL sin instalar nada,
  leyendo Parquet directamente.

### Bronze genérico, Silver por tabla

Bronze no tiene lógica por tabla: lee el CSV como texto y agrega metadata, así que es una
sola función parametrizada. Silver tiene una función por tabla porque las reglas son
específicas (rangos, valores válidos, claves foráneas distintas). Las transformaciones
genéricas viven en `transforms.py` y se testean aisladas; la composición por tabla vive
en `silver.py`.

### Estrategia de limpieza

- Claves (`customer_id`, `order_id`, ...): se descartan las filas con clave nula y se
  deduplica quedándose con la más reciente cuando hay fecha. Lo descartado va a
  quarantine con su razón.
- Integridad referencial: las filas con una FK que no existe en el padre se separan a
  quarantine; una FK nula se conserva, una referencia ausente aqui no se considera rota.
- Valores inválidos: categorías, status y tipos de pago fuera del set permitido se
  ponen a null y se registra el conteo. Números fuera de rango (precio negativo, score
  fuera de 1–5) se anulan o se separan según si el valor es central a la fila.
- Nulos descriptivos (nombre, email, ciudad): se conservan. No se imputan ni se descarta
  la fila; perder un cliente por no tener email es peor que el nulo.

## Observabilidad

Cada tabla genera un reporte de calidad en formato largo con el esquema:

```
check_name | table | column | records_checked | records_failed | pct_failed | stage | executed_at
```

Cubre nulos por columna, duplicados, casts fallidos, valores fuera de rango, valores no
permitidos, integridad referencial y filas de entrada frente a salida, indicando la etapa
en que se midió. Se persiste en `data/quality/` y se consolida en la tabla
`quality.checks` de DuckDB. Las filas descartadas quedan en `data/quarantine/` con la
columna `reject_reason`.

## Tests

`pytest` sobre las transformaciones críticas (parseo de fechas, casts permisivos, rangos,
dedup, integridad referencial, valores permitidos) y sobre el reporte de calidad. La
composición por tabla de Silver no se testea unitariamente por ser orquestación.

## Qué mejoraría con más tiempo

- Checks de calidad también en Gold (hoy solo hay en Bronze y Silver).
- Reconstruir el warehouse de forma atómica (build y swap) en vez de borrar y recrear el
  archivo en cada corrida.
- Tests de las tablas Gold y una prueba de integración del pipeline completo.
- Un flujo de ramas (una por feature y pull requests) en vez de trabajar todo sobre `main`.
