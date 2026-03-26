from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .build import build as build_distributable
from .export import export as export_csv_data
from .redbean import vacuum as vacuum_distributable


def _handle_error(error: Exception, verbose: bool) -> None:
    if verbose:
        raise error
    raise click.ClickException(str(error)) from error


@click.group()
@click.option("--verbose", is_flag=True, default=False, help="Show debug-level errors.")
@click.version_option(version=__version__, prog_name="csvpak")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command("build")
@click.option("--data", "data_path", required=False, type=click.Path(exists=True, path_type=Path))
@click.option("--schema", "schema_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.pass_context
def build_cmd(ctx: click.Context, data_path: Path | None, schema_path: Path, output_path: Path) -> None:
    verbose = bool(ctx.obj.get("verbose"))
    if data_path is None:
        click.echo("Parsing CSVW schema and initialising an empty SQLite database…")
    else:
        click.echo("Parsing CSVW schema and importing CSV data…")
    try:
        build_distributable(data=data_path, schema=schema_path, output=output_path)
    except Exception as error:
        _handle_error(error, verbose)
    click.echo(f"Build complete: {output_path}")


@cli.command("export")
@click.argument("distributable", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.pass_context
def export_cmd(ctx: click.Context, distributable: Path, output_path: Path) -> None:
    verbose = bool(ctx.obj.get("verbose"))
    click.echo("Exporting CSV from distributable…")
    try:
        row_count = export_csv_data(distributable=distributable, output=output_path)
    except Exception as error:
        _handle_error(error, verbose)
    click.echo(f"Export complete: {output_path} ({row_count} rows)")


@cli.command("vacuum")
@click.argument("distributable", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def vacuum_cmd(ctx: click.Context, distributable: Path) -> None:
    """Remove intermediary StoreAsset artefacts from DISTRIBUTABLE.

    Keeps only the original embedded database and the most-recent
    StoreAsset copy, discarding all intermediate versions.
    """
    verbose = bool(ctx.obj.get("verbose"))
    try:
        before, after = vacuum_distributable(distributable)
    except Exception as error:
        _handle_error(error, verbose)
    if before == after:
        click.echo(f"Nothing to do — {distributable} already has {before} data.sqlite entry/entries.")
    else:
        removed = before - after
        click.echo(f"Vacuumed {distributable}: removed {removed} intermediary entry/entries ({before} → {after}).")


def main() -> None:
    cli(obj={})
