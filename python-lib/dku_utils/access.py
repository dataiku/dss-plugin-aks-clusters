from collections import Mapping, Iterable
from six import text_type

def _get_in_object_or_array(o, chunk, d):
    if isinstance(chunk, int):
        if chunk >= 0 and chunk < len(o):
            return o[chunk] if o[chunk] is not None else d
        else:
            return d
    else:
        return o.get(chunk, d)

def _safe_get_value(o, chunks, default_value=None):
    if len(chunks) == 1:
        return _get_in_object_or_array(o, chunks[0], default_value) 
    else:
        return _safe_get_value(_get_in_object_or_array(o, chunks[0], {}), chunks[1:], default_value)

def _is_none_or_blank(x):
    return x is None or (isinstance(x, text_type) and len(x.strip()) == 0)

def _has_not_blank_property(d, k):
    return k in d and not _is_none_or_blank(d[k])
    
def _default_if_blank(x, d):
    if _is_none_or_blank(x):
        return d
    else:
        return x
    
def _default_if_property_blank(d, k, v):
    if not k in d:
        return v
    x = d[k]
    return _default_if_blank(x, v)

def _merge_objects(a, b):
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        r = {}
        ks = set(a.keys()).union(set(b.keys()))
        for k in ks:
            if k in b and k in a:
                r[k] = _merge_objects(a[k], b[k])
            elif k in b:
                r[k] = b[k]
            else:
                r[k] = a[k]
        return r
    elif isinstance(a, Iterable) and isinstance(b, Iterable):
        ret = []
        for x in a:
            ret.append(x)
        for x in b:
            ret.append(x)       
        return ret
    elif b is not None:
        return b
    else:
        return a
    
def kvl_to_dict(kvl):
    if kvl:
        d = {l["from"]: l["to"] for l in kvl}
        return d
    else:
        return None

def kvl_to_list(kvl):
    d = kvl_to_dict(kvl)
    if d:
        output = ["{}={}".format(k, d[k]) for k in d]
        return output
    else:
        return None

def collect_taints(node_pool_conf):
    taints_list = []
    if node_pool_conf.get("applyNodeTaints"):
        for effect in ["NoSchedule", "PreferNoSchedule", "NoExecute"]:
            taints_dict = kvl_to_dict(node_pool_conf.get(effect, None))
            if taints_dict:
                taints_list += ["{}={}:{}".format(k, taints_dict[k], effect ) for k in taints_dict]
    return taints_list
