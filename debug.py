from api import app

@app.after_request
def cb(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

