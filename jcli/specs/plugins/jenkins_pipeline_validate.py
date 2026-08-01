"""Jenkins Pipeline validate plugin: validate Jenkinsfile content."""
from cliyard.plugin import register_method


@register_method("jenkins_pipeline_validate")
def jenkins_pipeline_validate(params, http_client, config):
    """Validate a Jenkinsfile against the Jenkins server.

    Sends the Jenkinsfile content to the pipeline-model-converter endpoint
    and returns the validation result.

    Args:
        params: Dictionary containing 'jenkinsfile' key with file path.
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Parsed validation result (text or JSON).
    """
    jenkinsfile_path = params.get("jenkinsfile") or params.get("body", {}).get("jenkinsfile", "")
    if not jenkinsfile_path:
        return {"valid": False, "errors": ["No Jenkinsfile path provided"]}

    try:
        with open(jenkinsfile_path, "r", encoding="utf-8") as f:
            jenkinsfile_content = f.read()
    except Exception as e:
        return {"valid": False, "errors": [f"Failed to read Jenkinsfile: {e}"]}

    from urllib.parse import urlencode
    form_data = urlencode({"jenkinsfile": jenkinsfile_content})
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = http_client.request(
        "POST",
        "/pipeline-model-converter/validate",
        data=form_data,
        headers=headers,
    )
    
    try:
        return resp.json()
    except ValueError:
        text = resp.text.strip()
        if "Errors encountered" in text:
            lines = text.split('\n')
            errors = [line.strip() for line in lines[1:] if line.strip()]
            return {"valid": False, "errors": errors}
        elif "successfully validated" in text.lower():
            return {"valid": True, "message": text}
        else:
            return {"valid": None, "raw": text}