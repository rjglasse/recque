"""Entry point for RecQue web interface."""

import uvicorn


def main():
    uvicorn.run("recque_web.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
