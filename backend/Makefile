.PHONY: data-lite data-full gbm nn calibrate export eval api mock test scales cf-check

data-lite:
	uv run python -m pipeline.run --years 2014-2020

data-full:
	uv run python -m pipeline.run --years 1993-2020

gbm:
	uv run python -m model.train_gbm --cfg $(CFG)

nn:
	uv run python -m model.train_nn --cfg $(CFG)

calibrate:
	uv run python -m model.calibrate --model $(MODEL)

export:
	uv run python -m model.export --model $(MODEL)

eval:
	uv run python -m eval.evaluate

api:
	uv run uvicorn app.main:create_app --factory --reload

mock:
	uv run uvicorn mock:app --reload

test:
	uv run pytest -q

scales:
	uv run python scripts/make_scales.py

cf-check:
	uv run compliance-checker --test cf:1.10 data/cache/**/*.nc
