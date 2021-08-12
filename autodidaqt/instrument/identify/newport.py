import re


def esp_300_identify_resource(resource):
    try:
        response = resource.ask("TE?")
        if int(response) == 0:
            response.ask("ID? 1")
            resource.ask("TE?")
            return True
    except:
        pass
    finally:
        return False


idn_patterns = dict(
    [
        ["NewportESP301", re.compile(r"ESP30[012]")],
        ["NewportESP300", re.compile(r"ESP30[012]")],
    ]
)

identification_protocols = dict(
    [
        ["NewportESP301", esp_300_identify_resource],
        ["NewportESP300", esp_300_identify_resource],
    ]
)
