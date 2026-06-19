from electionsmaten import create_app, db


app = create_app()

# IMPORTANT: only initialize migrate once


if __name__ == "__main__":
    app.run(debug=True)