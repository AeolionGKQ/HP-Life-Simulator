"""Create the disposable SQLite schema used by the build-time test run."""

from backend.app.db.session import initialize_database


def main() -> None:
    initialize_database()


if __name__ == "__main__":
    main()
