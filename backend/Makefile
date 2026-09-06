.PHONY: data-lite data-full synth gbm nn calibrate export eval api mock test scales cf-check

data-lite:
	uv run python -m pipeline.run --years 2014-2020

data-full:
	uv run python -m pipeline.run --years 1993-2020

synth:
	uv run python -m pipeline.run --synthetic --start 2014-01-01 --end 2020-12-31 --ny 100 --nx 240

gbm:
	uv run python -m model.train_gbm --cfg configs/gbm.yaml --rows $(or $(ROWS),lite)

nn:
	uv run python -m model.train_nn --cfg $(or $(CFG),configs/lite.yaml)

calibrate:
	uv run python -m model.calibrate --cfg $(or $(CFG),configs/lite.yaml)

export:
	uv run python -m model.export --model $(or $(MODEL),lite) --cfg $(or $(CFG),configs/lite.yaml)

eval:
	uv run python -m eval.evaluate --models $(or $(MODELS),climatology,gbm,lite)

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
