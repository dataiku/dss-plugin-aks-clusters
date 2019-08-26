from msrestazure.azure_exceptions import CloudError

def run_and_process_cloud_error(fn):
    try:
        return fn()
    except CloudError as e:
        raise Exception('%s : %s' % (str(e), e.response.content))
    except Exception as e:
        raise e