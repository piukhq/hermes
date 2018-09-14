def accept_version(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        # This code checks the accept header used for banking app and
        #   1)  rewites it as application/json
        #   2)  sets request.version to parameter v=,  ver= or version=  note v= is in spec but version= is more standard
        #   3)  Adds /ubiquity to path so as it maps to document

        accept = request.META.get('HTTP_ACCEPT')
        version_number = '1.0'
        if accept[0:25] == 'application/vnd.bink+json':
            try:
                accept, version = accept.split(";")
                if version[0:1] == 'v':                  # allow any parameter starting with v eg v= , ver=, version=
                    _, version_number = version.split('=')
            except ValueError:
                pass
            request.META['HTTP_ACCEPT'] = 'application/json;version={}'.format(version_number)
            request.path_info = '/ubiquity{}'.format(request.path_info)
            request.path = '/ubiquity{}'.format(request.path)

        response = get_response(request)


        return response

    return middleware