"""Run the dashboard API with `python -m dashboard_api`."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("dashboard_api.app:app", host="127.0.0.1", port=8008, reload=True)

