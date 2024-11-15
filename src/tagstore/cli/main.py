import typer

from ...tagpack import __version__

app = typer.Typer()


@app.command()
def version():
    print(__version__)


def main():
    app()


if __name__ == "__main__":
    main()
