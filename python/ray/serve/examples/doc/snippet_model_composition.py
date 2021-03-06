from random import random
import requests
import ray
from ray import serve

ray.init(num_cpus=8)
client = serve.start()

# Our pipeline will be structured as follows:
# - Input comes in, the composed model sends it to model_one
# - model_one outputs a random number between 0 and 1, if the value is
#   greater than 0.5, then the data is sent to model_two
# - otherwise, the data is returned to the user.

# Let's define two models that just print out the data they received.


def model_one(request):
    print("Model 1 called with data ", request.args.get("data"))
    return random()


def model_two(request):
    print("Model 2 called with data ", request.args.get("data"))
    return request.args.get("data")


class ComposedModel:
    def __init__(self):
        client = serve.connect()
        self.model_one = client.get_handle("model_one")
        self.model_two = client.get_handle("model_two")

    # This method can be called concurrently!
    async def __call__(self, flask_request):
        data = flask_request.data

        score = await self.model_one.remote(data=data)
        if score > 0.5:
            result = await self.model_two.remote(data=data)
            result = {"model_used": 2, "score": score}
        else:
            result = {"model_used": 1, "score": score}

        return result


client.create_backend("model_one", model_one)
client.create_endpoint("model_one", backend="model_one")

client.create_backend("model_two", model_two)
client.create_endpoint("model_two", backend="model_two")

# max_concurrent_queries is optional. By default, if you pass in an async
# function, Ray Serve sets the limit to a high number.
client.create_backend(
    "composed_backend", ComposedModel, config={"max_concurrent_queries": 10})
client.create_endpoint(
    "composed", backend="composed_backend", route="/composed")

for _ in range(5):
    resp = requests.get("http://127.0.0.1:8000/composed", data="hey!")
    print(resp.json())
# Output
# {'model_used': 2, 'score': 0.6250189863595503}
# {'model_used': 1, 'score': 0.03146855349621436}
# {'model_used': 2, 'score': 0.6916977560006987}
# {'model_used': 2, 'score': 0.8169693450866928}
# {'model_used': 2, 'score': 0.9540681979573862}
