"""Loading, normalizing and saving WireMock mapping files, plus example stubs."""

import json
import uuid

from api_tool.core.stubs.matching import url_spec
from api_tool.core.stubs.model import DEFAULT_PRIORITY, new_stub, TEMPLATE_TRANSFORMER
from api_tool.core.stubs.webhooks import _normalize_webhook, set_webhooks


def normalize_stub(stub):
    """Fill in defaults and convert WireMock-only shapes into what the editor understands."""
    stub = json.loads(json.dumps(stub))  # deep copy, JSON-safe
    if not isinstance(stub.get("id"), str) or not stub["id"]:
        stub["id"] = str(uuid.uuid4())
    if not isinstance(stub.get("priority"), int) or isinstance(stub.get("priority"), bool):
        stub["priority"] = DEFAULT_PRIORITY
    for section in ("request", "response", "metadata"):
        if not isinstance(stub.get(section), dict):
            stub[section] = {}
    if not stub["metadata"]:
        del stub["metadata"]
    request = stub["request"]
    if not isinstance(request.get("method"), str) or not request["method"]:
        request["method"] = "ANY"
    for field in ("queryParameters", "headers"):
        if field in request and not isinstance(request[field], dict):
            del request[field]
    if "bodyPatterns" in request and not isinstance(request["bodyPatterns"], list):
        del request["bodyPatterns"]
    response = stub["response"]
    if not isinstance(response.get("status"), int) or isinstance(response.get("status"), bool):
        response["status"] = 200
    if "headers" in response and not isinstance(response["headers"], dict):
        del response["headers"]
    if "transformers" in response and not isinstance(response["transformers"], list):
        del response["transformers"]
    # WireMock 2 called webhooks postServeActions; WireMock 3 uses serveEventListeners.
    listeners = stub.get("serveEventListeners")
    listeners = [l for l in listeners if isinstance(l, dict)] if isinstance(listeners, list) else []
    legacy = stub.pop("postServeActions", None)
    if isinstance(legacy, list):
        listeners += [l for l in legacy if isinstance(l, dict)]
    elif isinstance(legacy, dict):  # very old map form: {"webhook": {...}}
        listeners += [{"name": name, "parameters": params} for name, params in legacy.items()]
    for listener in listeners:
        if listener.get("name") == "webhook":
            listener["parameters"] = _normalize_webhook(listener.get("parameters"))
    if listeners:
        stub["serveEventListeners"] = listeners
    else:
        stub.pop("serveEventListeners", None)
    if "metadata" in stub and not isinstance(stub["metadata"].get("script", ""), str):
        del stub["metadata"]["script"]
    if "jsonBody" in response:
        response["body"] = json.dumps(response.pop("jsonBody"), indent=2)
        headers = response.setdefault("headers", {})
        if not any(k.lower() == "content-type" for k in headers):
            headers["Content-Type"] = "application/json"
    if not stub.get("name"):
        _, url = url_spec(request)
        stub["name"] = f"{request['method']} {url or '(any URL)'}"
    return stub


def load_mappings(text):
    """Accept {"mappings": [...]}, a bare list of mappings, or a single mapping object."""
    data = json.loads(text)
    if isinstance(data, dict) and "mappings" in data:
        data = data["mappings"]
    elif isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Expected {\"mappings\": [...]}, a list of mappings, or one mapping")
    stubs = [normalize_stub(stub) for stub in data if isinstance(stub, dict)]
    seen = set()
    for stub in stubs:
        if stub["id"] in seen:
            stub["id"] = str(uuid.uuid4())
        seen.add(stub["id"])
    return stubs


def dump_mappings(stubs):
    return json.dumps({"mappings": stubs}, indent=2)


def example_stubs(base_url):
    """Ready-made stubs showing templates, scripts, and webhooks; base_url is this server's address."""
    echo = new_stub(name="Example: echo request values (templates)", method="POST")
    echo["request"] = {"method": "POST", "urlPathPattern": "/api/echo/[^/]+"}
    echo["response"]["transformers"] = [TEMPLATE_TRANSFORMER]
    echo["response"]["body"] = (
        '{\n'
        '  "id": "{{request.path.[2]}}",\n'
        '  "user": "{{request.query.user default=\'guest\'}}",\n'
        '  "token": "{{request.headers.X-Token}}",\n'
        '  "customer": "{{jsonPath request.body \'$.customer.name\'}}",\n'
        '  "firstSku": "{{request.json.items.[0].sku}}",\n'
        '  "receivedAt": "{{now}}",\n'
        '  "requestId": "{{uuid}}"\n'
        '}'
    )

    secure = new_stub(name="Example: require X-Token header (script)", url_path="/api/secure")
    secure["response"]["body"] = '{\n  "message": "{{vars.greeting}}",\n  "role": "{{vars.role}}"\n}'
    secure["metadata"] = {"script": (
        "# 401 unless the caller sends X-Token\n"
        "token = request.headers.get(\"X-Token\")\n"
        "if not token:\n"
        "    response.status = 401\n"
        "    response.json = {\"error\": \"Send an X-Token header\"}\n"
        "else:\n"
        "    user = request.query.get(\"user\", \"friend\")\n"
        "    vars[\"greeting\"] = f\"Welcome, {user}!\"\n"
        "    vars[\"role\"] = \"admin\" if token == \"admin-token\" else \"viewer\"\n"
        "    print(\"token ok for\", user)\n"
    )}

    receiver = new_stub(name="Example: webhook receiver", method="POST", url_path="/api/order-events")
    receiver["response"]["body"] = '{\n  "received": true\n}'

    order = new_stub(name="Example: create order + webhook", method="POST", url_path="/api/orders")
    order["response"]["status"] = 202
    order["response"]["transformers"] = [TEMPLATE_TRANSFORMER]
    order["response"]["body"] = (
        '{\n  "orderId": "{{vars.orderId}}",\n  "status": "processing",\n'
        '  "note": "A webhook will report status=shipped in 3 seconds"\n}'
    )
    order["metadata"] = {"script": 'vars["orderId"] = "ORD-" + str(random.randint(1000, 9999))\n'}
    set_webhooks(order, [{
        "method": "POST",
        "url": f"{base_url}/api/order-events",
        "queryParameters": {"orderId": "{{vars.orderId}}", "customer": "{{jsonPath request.body '$.customer'}}"},
        "headers": {"Content-Type": "application/json", "X-Event": "order.shipped"},
        "body": (
            '{\n  "orderId": "{{vars.orderId}}",\n  "status": "shipped",\n'
            '  "customer": "{{jsonPath originalRequest.body \'$.customer\'}}",\n'
            '  "firstResponseStatus": {{response.status}}\n}'
        ),
        "delay": {"type": "fixed", "milliseconds": 3000},
    }])
    return [echo, secure, order, receiver]
