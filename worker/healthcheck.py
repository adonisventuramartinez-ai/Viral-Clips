"""Lo usa Docker (HEALTHCHECK): sale con 0 si el worker marcó que sigue vivo hace menos de 3 minutos."""
import sys

import lifecycle

age = lifecycle.alive_age()
sys.exit(0 if age is not None and age < 180 else 1)
