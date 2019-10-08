from user.models import ClientApplicationBundle
from scheme.models import SchemeBundleAssociation
from rest_framework import exceptions
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import Q


class Permit:
    AVAILABLE = 1
    SUSPENDED = 2
    ACTIVE = 3

    def __init__(self, bundle_id=None, client=None, organisation_name=None, service_allow_all=False, ubiquity=False,
                 user=None):
        """This class is instantiated during authentication and should be passed via request object to allow query
        filtering and channel status testing
        Each group of users belongs to a client application which belongs to one organisation.
        A client application can have one or more Channels to select which schemes and actions on schemes are permitted
        A channel is referred to in code as a client application bundle and has a bundle id string to identify it.
        We are keeping the bundle name because this makes sense of the names used in tokens etc.
        :param bundle_id: String identifier for a channel
        :param client:  client application
        :param organisation_name: Organisation eg Barclays, Loyality Angels
        :param user: User model

        Bundle_id and client are unique together but Ubiquity token only defines Organisation and bundle id.
        During configuration for Ubiquity an Organisation must use unique bundle ids to prevent blocking authentication.
        """
        self.found_schemes_status = {}
        self.found_issuers_status = {}
        self.looked_up_bundle = None
        self.client = client
        self.user = user
        self.bundle_id = bundle_id
        self.ubiquity = ubiquity     # Used to invoke special logic for Ubiquity e.g. making suspended same as inactive

        # This forces an active permit regardless of scheme for inter-service calls.  However trying to get a bundle
        # object will return None.  Generally outside of authentication, getting bundle from Permit is not required as
        # it is best use one of the high level checks
        self.service_allow_all = service_allow_all

        if user:
            self.client = user.client

        if not self.client and not organisation_name and not self.service_allow_all:
            raise exceptions.AuthenticationFailed('Invalid Token')

        elif organisation_name and not client:
            # Ubiquity tokens supplies credentials for bundle_id and organisation_name and these need to be verified
            # to permit authentication to continue
            try:
                self.looked_up_bundle = ClientApplicationBundle\
                    .objects.get(bundle_id=bundle_id, client__organisation__name=organisation_name)
                self.client = self.looked_up_bundle.client
            except ObjectDoesNotExist:
                raise KeyError
            except MultipleObjectsReturned:
                # This should not occur after release as unique together constraint has been added in a migration
                # Covers edge case of duplicate already exists which would cause the unique together migration to fail
                # then this error message will help debug
                raise exceptions.AuthenticationFailed(f"Multiple '{self.bundle_id}'"
                                                      f" bundle ids for client '{self.client}'")
            self.client = self.looked_up_bundle.client

        elif self.client and not bundle_id:
            try:
                self.bundle_id = ClientApplicationBundle.objects.values_list('bundle_id',
                                                                             flat=True).get(client=self.client)
            except MultipleObjectsReturned:
                raise exceptions.AuthenticationFailed(f"Undefined bundle_id could not be resolved as there"
                                                      f" multiple bundle ids for client '{self.client}'")

    @staticmethod
    def is_authenticated():
        """
        This allows the Permit to act like Bundle object in always allowing authentication i.e. the class is mainly
        with authorisation and filtering of queries to allow authorised items

        :return: True
        """
        return True

    @property
    def bundle(self):
        if self.service_allow_all:
            return None
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

    def scheme_suspended(self, relation=''):
        return {f'{relation}schemebundleassociation__status': SchemeBundleAssociation.SUSPENDED}

    def scheme_query(self, query, allow=None):
        return self.related_model_query(query, '', allow)

    def scheme_account_query(self, query, allow=None):
        return self.related_model_query(query, 'scheme__', allow)

    def scheme_payment_account_query(self, query, allow=None):
        return self.related_model_query(query, 'scheme_account_set__scheme__', allow)

    def related_model_query(self, query, relation='', allow=None):
        if self.service_allow_all:
            return query
        bundle_root = f'{relation}schemebundleassociation__'
        status_key = f'{bundle_root}status'
        bundle = {f'{bundle_root}bundle': self.bundle}
        active = {status_key: SchemeBundleAssociation.ACTIVE}
        suspended = {status_key: SchemeBundleAssociation.SUSPENDED}
        q = Q(**bundle)

        if allow == self.AVAILABLE or allow is None:
            # By default permit query filter selects only defined schemes which are not inactive
            # thus inactive is the same as not defined
            if self.ubiquity:
                q = q & Q(**active)
            else:
                q = q & (Q(**active) | Q(**suspended))
        elif allow == self.SUSPENDED:
            if self.ubiquity:
                q = q & Q(**active)
            else:
                q = q & (Q(**active) | Q(**suspended))
        elif allow == self.ACTIVE:
            q = q & Q(**active)

        return query.filter(q)

    def is_scheme_suspended(self, scheme_id):
        return self.scheme_status(scheme_id) == SchemeBundleAssociation.SUSPENDED

    def is_scheme_active(self, scheme_id):
        return self.scheme_status(scheme_id) == SchemeBundleAssociation.ACTIVE

    def is_scheme_available(self, scheme_id):
        status = self.scheme_status(scheme_id)
        return status is not None and status != SchemeBundleAssociation.INACTIVE

    def scheme_status_name(self, scheme_id, active='active', suspended='suspended', in_active='in_active'):
        label = in_active
        status = self.scheme_status(scheme_id)
        if status == SchemeBundleAssociation.ACTIVE:
            label = active
        elif status == SchemeBundleAssociation.SUSPENDED:
            label = suspended
        return label

    def scheme_status(self, scheme_id):
        if self.service_allow_all:
            return SchemeBundleAssociation.ACTIVE
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
        if self.ubiquity and status == SchemeBundleAssociation.SUSPENDED:
            status = SchemeBundleAssociation.INACTIVE
        return status
