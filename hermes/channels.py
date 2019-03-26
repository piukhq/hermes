from user.models import ClientApplicationBundle
from scheme.models import SchemeBundleAssociation
from rest_framework import exceptions
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned


class Permit:

    def __init__(self, bundle_id, client=None, organisation_name=None):
        """This class is instantiated during authentication and should
        :param bundle_id: String identifier for what is now considerred to be a channel (we keep original name as used
        in tokens)
        :param client: The object defining the
        :param organisation_name:
        """
        self.found_schemes_status = {}
        self.found_issuers_status = {}
        self.looked_up_bundle = None
        self.client = client
        self.bundle_id = bundle_id
        if not client and not organisation_name:
            raise exceptions.AuthenticationFailed('Invalid Token')
        elif organisation_name and not client:
            # Ubiquity tokens supplies credentials for bundle_id and organisation_name and these need to be verified
            # to permit authentication to continue
            try:
                self.looked_up_bundle = ClientApplicationBundle\
                    .objects.get(bundle_id=bundle_id, client__organisation__name=organisation_name)
            except ObjectDoesNotExist:
                raise KeyError
            except MultipleObjectsReturned:
                # This should not occur after release as unique together constraint has been added in a migration
                # Covers edge case of duplicate already exists which would cause the unique together migration to fail
                # then this error message will help debug
                raise exceptions.AuthenticationFailed(f"Multiple '{self.bundle_id}'"
                                                      f" bundle ids for client '{self.client}'")
            self.client = self.looked_up_bundle.client

    @property
    def bundle(self):
        # Bundle will only be looked up when required and only once per request
        if not self.looked_up_bundle:
            try:
                self.looked_up_bundle = ClientApplicationBundle.objects.get(bundle_id=self.bundle_id,
                                                                            client=self.client)
            except ObjectDoesNotExist:
                raise exceptions.AuthenticationFailed('Bundle Id not configured for client')
            except MultipleObjectsReturned:
                # This should not occur after release as unique together constraint has been added in a migration
                # Covers edge case of duplicate already exists which would cause the unique together migration to fail
                # then this error message will help debug
                raise exceptions.AuthenticationFailed(f"Multiple '{self.bundle_id}'"
                                                      f" bundle ids for client '{self.client}'")
        return self.looked_up_bundle

    def scheme_query(self, query, excludes=None, includes=None):
        return self.related_model_query(query, '', excludes, includes)

    def scheme_account_query(self, query, excludes=None, includes=None):
        return self.related_model_query(query, 'scheme__', excludes, includes)

    def related_model_query(self, query, relation='', excludes=None, includes=None):
        filters = {f'{relation}schemebundleassociation__bundle': self.bundle}
        status_key = f'{relation}schemebundleassociation__status'
        if includes:
            for inc in includes:
                filters[status_key] = inc
        query = query.filter(**filters)
        filters = {}
        if excludes:
            for ex in excludes:
                filters[status_key] = ex
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
