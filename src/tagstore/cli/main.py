from typing import Optional

import typer

from tagpack import __version__

from ..config import TagstoreSettings
from ..db.database import (
    get_db_engine,
    get_table_ddl_sql,
    get_views_ddl_sql,
    init_database,
)

app = typer.Typer()


@app.command("version")
def version():
    print(__version__)


@app.command("init")
def init(db_url: Optional[str] = None):
    db_url_settings = TagstoreSettings().db_url
    init_database(get_db_engine(db_url or db_url_settings))


@app.command("get-create-sql")
def get_ddl():
    print(get_table_ddl_sql())

    print(get_views_ddl_sql())


def main():
    # Deprecation warning
    import sys
    print("⚠️  DEPRECATION WARNING: gs-tagstore-cli is deprecated!", file=sys.stderr)
    print("   This tool has been moved to graphsense-lib.", file=sys.stderr)
    print("   Please install graphsense-lib and use: graphsense-cli tagstore", file=sys.stderr)
    print("   For more information: https://github.com/graphsense/graphsense-lib", file=sys.stderr)
    print("", file=sys.stderr)
    
    app()


if __name__ == "__main__":
    main()
