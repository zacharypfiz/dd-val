UV=uv

.PHONY: seed validate score

seed:
	$(UV) run -q dd-seed --out corpus --projects 10 --rows 500 --seed 42

validate:
	bash scripts/validate_all.sh

score:
	$(UV) run -q dd-score --corpus corpus --mode variable

