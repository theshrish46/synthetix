from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


from graph import graph

app = graph.compile()


console = Console(color_system="windows")

console.rule("[bold cyan]Synthetix Execution Trace", characters="=")
input = console.input("Enter the [bold green]GitHub Repo[/] link : ")

# 2. Use a "Live" display for the spinner
with console.status(
    "[bold green]Agent is navigating the graph...", spinner="bouncingBar"
) as status:

    final_state = {}  # We'll store the last state here to print the final summary

    # 3. Start the stream
    for event in app.stream({"repo_url": input, "base_branch": "main"}):
        # event is a dict: {"NodeName": {updated_state_keys}}
        for node_name, state_update in event.items():

            # --- DISCOVERY PHASE ---
            if node_name == "Discovery":
                console.rule("[bold magenta]Discovery Node Finished")
                table = Table(
                    title="Files identified for refactoring",
                    header_style="bold magenta",
                )
                table.add_column("Path", style="dim")
                table.add_column("Language", justify="right")

                for file in state_update["files_to_process"]:
                    ext = file.split(".")[-1]
                    table.add_row(file, ext.upper())
                console.print(table)

            # --- SELECTOR PHASE ---
            elif node_name == "Selector":
                current_file = state_update["current_file"]
                console.print(f"📦 [bold blue]Targeted:[/] {current_file}")

            # --- REFRACTOR PHASE ---
            elif node_name == "Refractor":
                # Note: Refractor updates repo_data. We can pull info from there.
                console.print(
                    f"🛠️  [bold yellow]Refactored logic for current file...[/]"
                )

            # --- REVIEWER PHASE ---
            elif node_name == "Reviewer":
                # Get the score for the file we just processed
                current_file = state_update.get("current_file") or final_state.get(
                    "current_file"
                )
                file_data = state_update["repo_data"][current_file]
                score = file_data["review"]["score"]

                color = "green" if score >= 0.7 else "red"
                console.print(f"⭐ [bold {color}]Review Score:[/] {score}/1.0")
                console.print(
                    f"📝 [italic dim]Feedback: {file_data['review']['feedback']}[/]"
                )
                console.print("-" * 30)

            # --- PR MANAGER PHASE ---
            elif node_name == "PR_Manager":
                console.rule("[bold green]Mission Accomplished")
                pr_url = state_update.get("pr_url", "URL not found")
                console.print(
                    Panel(
                        f"Pull Request Raised: [bold link]{pr_url}[/]",
                        border_style="green",
                    )
                )

            # Keep track of the full state
            final_state.update(state_update)
