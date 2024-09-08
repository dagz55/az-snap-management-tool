import asyncio
import json
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich import box

console = Console()

async def run_az_command(command):
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return stdout.decode().strip()
        else:
            console.print(f"[red]Error running command: {command}[/red]")
            console.print(f"[red]Error message: {stderr.decode().strip()}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]An error occurred: {str(e)}[/bold red]")
        return None

async def get_subscriptions():
    result = await run_az_command("az account list --query '[].{name:name, id:id}' -o json")
    if result:
        return json.loads(result)
    return []

async def get_snapshots(subscription_id, start_date, end_date):
    command = f"az snapshot list --subscription {subscription_id} --query '[?timeCreated>=`{start_date}` && timeCreated<=`{end_date}`].{{name:name, resourceGroup:resourceGroup, timeCreated:timeCreated, diskSizeGb:diskSizeGb, id:id, diskState:diskState, createdBy:managedBy}}' -o json"
    result = await run_az_command(command)
    if result:
        return json.loads(result)
    return []

def display_snapshots(snapshots, subscription_name):
    if not snapshots:
        console.print(f"[yellow]No snapshots found in subscription: {subscription_name}[/yellow]")
        return

    table = Table(title=f"Snapshots in {subscription_name}", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Resource Group", style="magenta")
    table.add_column("Time Created", style="green")
    table.add_column("Size (GB)", justify="right")
    table.add_column("State", style="blue")
    table.add_column("Created By", style="yellow")

    for snapshot in snapshots:
        table.add_row(
            snapshot['name'],
            snapshot['resourceGroup'],
            snapshot['timeCreated'],
            str(snapshot['diskSizeGb']),
            snapshot['diskState'],
            snapshot['createdBy'] if snapshot['createdBy'] else "N/A"
        )

    console.print(table)

def get_default_date_range():
    today = datetime.now(timezone.utc)
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    return start_of_month.isoformat(), end_of_month.isoformat()

async def main():
    console.print("[bold cyan]Welcome to the Azure Snapshot Finder![/bold cyan]")

    # Get date range from user or use default
    default_start, default_end = get_default_date_range()
    start_date = Prompt.ask("Enter start date (YYYY-MM-DD)", default=default_start[:10])
    end_date = Prompt.ask("Enter end date (YYYY-MM-DD)", default=default_end[:10])

    # Validate and format dates
    try:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        start_date = start_datetime.isoformat()
        end_date = end_datetime.isoformat()
    except ValueError:
        console.print("[bold red]Invalid date format. Using default date range for the current month.[/bold red]")
        start_date, end_date = default_start, default_end

    subscriptions = await get_subscriptions()
    if not subscriptions:
        console.print("[bold red]No subscriptions found. Please make sure you're logged in with 'az login'.[/bold red]")
        return

    all_snapshots = []

    for subscription in subscriptions:
        console.print(f"\n[bold blue]Searching in subscription: {subscription['name']}[/bold blue]")
        snapshots = await get_snapshots(subscription['id'], start_date, end_date)
        display_snapshots(snapshots, subscription['name'])
        all_snapshots.extend(snapshots)

    # Display summary table
    summary_table = Table(title="Snapshot Summary", box=box.ROUNDED)
    summary_table.add_column("Snapshot Name", style="cyan")
    summary_table.add_column("Date Created", style="green")
    summary_table.add_column("Status", style="magenta")
    summary_table.add_column("Created By", style="yellow")

    for snapshot in all_snapshots:
        summary_table.add_row(
            snapshot['name'],
            snapshot['timeCreated'],
            "Attached" if snapshot['diskState'] == "Attached" else "Unattached",
            snapshot['createdBy'] if snapshot['createdBy'] else "N/A"
        )

    console.print("\n[bold green]Snapshot Summary:[/bold green]")
    console.print(summary_table)

    console.print(f"\n[bold green]Total snapshots found: {len(all_snapshots)}[/bold green]")
    console.print("\n[bold green]Snapshot search complete![/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
