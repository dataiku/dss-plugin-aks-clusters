import json, logging
from dku_utils.access import _is_none_or_blank

class Taint(dict):
    def __init__(self, taint):
        logging.debug("Creating taint from '%s'" % json.dumps(taint))
        if isinstance(taint, str):
            logging.debug("Taint is a raw string, it requires parsing.")
            try:
                key_value, effect = taint.split(':')
                if '=' in key_value:
                    key, value = key_value.split('=')
                else:
                    key = key_value
                    value = None  # Set value to None if it's not provided
                self["key"] = key
                self["value"] = value
                self["effect"] = effect
            except ValueError as e:
                raise ValueError(
                    f"Invalid taint format: '{taint}'. Expected format '<key>[=<value>]:<effect>'"
                ) from e
        else:
            logging.debug("Taint is an object, it requires extracting.")
            if not _is_none_or_blank(taint.get("key", None)):
                self["key"] = taint.get("key", "")

            if not _is_none_or_blank(taint.get("value", None)):
                self["value"] = taint.get("value", "")

            if not _is_none_or_blank(taint.get("effect", None)):
                self["effect"] = taint.get("effect", "")

    def __eq__(self, other):
        return (
            self.get("key", "") == other.get("key", "")
            and self.get("value", "") == other.get("value", "")
            and self.get("effect", "") == other.get("effect", "")
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.get("key", ""), self.get("value", ""), self.get("effect", "")))


class Toleration(Taint):
    def __init__(self, taint):
        super(Toleration, self).__init__(taint)

        if self.get("value", ""):
            self["operator"] = "Equal"
        else:
            self["operator"] = "Exists"

    def __eq__(self, other):
        return super(Toleration, self).__eq__(other) and self.get("operator", "") == other.get("operator", "")

    def __hash__(self):
        return hash((super(Toleration, self).__hash__(), self.get("operator", "")))

    def to_dict(self):
        return {k: v for k, v in self.items()}

    @staticmethod
    def from_json(tolerations_json):
        return [Toleration(tol) for tol in json.loads(tolerations_json)]

    @staticmethod
    def from_dict(raw_dicts):
        return [Toleration(raw) for raw in raw_dicts or []]

    @staticmethod
    def to_list(tolerations):
        return [toleration.to_dict() for toleration in tolerations]

    @staticmethod
    def from_taints_config(taints):
        return [Toleration(t) for t in taints]
