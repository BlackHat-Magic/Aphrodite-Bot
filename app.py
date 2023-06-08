from website import start
import hypercorn.asyncio

app, discord = start()

# run the app
if(__name__ == "__main__"):
	app.run(host="0.0.0.0", debug=True)