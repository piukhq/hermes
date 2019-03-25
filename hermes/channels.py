from user.models import ClientApplicationBundle
from scheme.models import SchemeBundleAssociation
from rest_framework import exceptions
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned


class Permit:

    def __init__(self, bundle_id, client=None):
        self.found_schemes_status = {}
        self.found_issuers_status = {}
        self.looked_up_bundle = None
        self.client = client
        self.bundle_id = bundle_id

    @property
    def bundle(self):
        # Bundle will only be looked up when required and only once per request
        if not self.looked_up_bundle:
            try:
                self.looked_up_bundle = ClientApplicationBundle.objects.get(bundle_id=self.bundle_id,
                                                                            client=self.client)
            except ObjectDoesNotExist:
                raise exceptions.AuthenticationFailed('Bundle Id not configured')
            except MultipleObjectsReturned:
                # This should not occur after release as unique together constraint has been added in a migration
                # Covers edge case of duplicate already exists which would cause the unique together migration to fail
                # then this error message will help debug
                raise exceptions.AuthenticationFailed(f"Multiple '{self.bundle_id}'"
                                                      f" bundle ids for client '{self.client}'")
        return self.looked_up_bundle

    def scheme_query(self, query, excludes=None, includes=None):
            filters = {'schemebundleassociation__bundle': self.bundle}
            if includes:
                for inc in includes:
                    filters['schemebundleassociation__status'] = inc
            query = query.filter(**filters)
            filters = {}
            if excludes:
                for ex in excludes:
                    filters['schemebundleassociation__status'] = ex
                query.exclude(**filters)
            return query

    def scheme_account_query(self, query, excludes=None, includes=None):
            filters = {'scheme__schemebundleassociation__bundle': self.bundle}
            if includes:
                for inc in includes:
                    filters['scheme__schemebundleassociation__status'] = inc
            query = query.filter(**filters)
            filters = {}
            if excludes:
                for ex in excludes:
                    filters['scheme__schemebundleassociation__status'] = ex
                query.exclude(**filters)
            return query

    def scheme_status(self, scheme_id):
        # Scheme status will only be looked up when required and only once per request per scheme
        if scheme_id in self.found_schemes_status:
            return self.found_schemes_status[scheme_id]
        status_list = SchemeBundleAssociation.\
            objects.filter(bundle__bundle_id=self.bundle_id, scheme_id=scheme_id).values('status')
        if len(status_list) > 1:
            raise exceptions.AuthenticationFailed(f"Channels id ='{self.bundle_id}' has "
                                                  f"multiple entries for scheme id '{scheme_id}'")
        if status_list:
            status = status_list[0]['status']
        else:
            status = None

        self.found_schemes_status[scheme_id] = status
        return status

    def issuer_status(self, issuer_id):
        # Scheme status will only be looked up when required and only once per request per scheme
        if issuer_id in self.found_issuers_status:
            return self.found_issuers_status[issuer_id]
        if ClientApplicationBundle.objects.filter(bundle__bundle_id=self.bundle_id, issuer_id=issuer_id).exists():
            status = 0
        else:
            status = None
        self.found_issuers_status[issuer_id] = status
        return status


    """
    permit = request.channels_permit

        print(permit.scheme_status(105))
        print(permit.scheme_status(110))
        print(permit.scheme_status(100))
        print(permit.scheme_status(88))
        print(permit.scheme_status(105))
        print(permit.scheme_status(110))
        print(permit.scheme_status(100))
        print(permit.scheme_status(88))

        #setattr(request, 'allowed_issuers', [issuer.pk for issuer in bundle.issuer.all()])
        #setattr(request, 'allowed_schemes', [scheme.pk for scheme in bundle.scheme.all()])


    """