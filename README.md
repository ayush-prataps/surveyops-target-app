# surveyops-target-app

Synthetic multi-service backend (orders, payment, inventory, auth) used as the system under diagnosis for SurveyOps. It contains deliberate weaknesses. Do not fix them by hand.

## Run tests
pip install -r requirements-dev.txt
pytest tests/

## Rules
- main is protected. Changes arrive through pull requests only.
- Contains no real data, no secrets.