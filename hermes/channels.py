import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import Q
from rest_framework import exceptions

from scheme.models import SchemeBundleAssociation
from user.models import ClientApplicationBundle

logger = logging.getLogger(__name__)


class Permit:
    AVAILABLE = 1
    SUSPENDED = 2
    ACTIVE = 3

    def __init__(self, bundle_id=None, client=None, organisation_name=None, service_allow_all=False, ubiquity=False,
                 user=None, auth_by='external'):
        """This class is instantiated during authentication and should be passed via request object to allow query
        filtering and channel status testing
        Each group of users belongs to a client application which belongs to one organisation.
        A client application can have one or more Channels to select which schemes and actions on schemes are permitted
        A channel is referred to in code as a client application bundle and has a bundle id string to identify it.
        We are keeping the bundle name because this makes sense of the names used in tokens etc.
        :param bundle_id: String identifier for a channel
        :param client:  client application
        :param organisation_name: Organisation eg Barclays, Loyalty Angels
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
        self.ubiquity = ubiquity  # Used to invoke special logic for Ubiquity e.g. making suspended same as inactive
        self.auth_by = auth_by

        # This forces an active permit regardless of scheme for inter-service calls.
        self.service_allow_all = service_allow_all
        if bundle_id == settings.INTERNAL_SERVICE_BUNDLE:
            self.service_allow_all = True

        # User is defined with client to server permits
        if user and not self.client:
            self.client = user.client

        self._authenticate_bundle(organisation_name, bundle_id)

    def _authenticate_bundle(self, organisation_name, bundle_id):
        if not self.client and not organisation_name and not self.service_allow_all:
            raise exceptions.AuthenticationFailed('Invalid Token')
        elif organisation_name and not self.client:
            self._init_server_to_server(organisation_name)
        elif self.client and not bundle_id:
            # This occurs if an old client to server token without client or bundle_id is encountered.
            try:
                self.bundle_id = ClientApplicationBundle.objects.values_list('bundle_id',
                                                                             flat=True).get(client=self.client)
            except MultipleObjectsReturned:
                logger.error(f"There are multiple bundle ids for client '{self.client}' due to a configuration error"
                             "Error found in channels.py when trying to "
                             "find a bundle_id using client because it was not in the token")
                raise exceptions.AuthenticationFailed('Invalid Token')

    def _init_server_to_server(self, organisation_name):
        # Ubiquity tokens supplies credentials for bundle_id and organisation_name and these need to be verified
        # to permit authentication to continue
        try:
            self.looked_up_bundle = ClientApplicationBundle.get_bundle_by_bundle_id_and_org_name(
                self.bundle_id, organisation_name)
            self.client = self.looked_up_bundle.client
        except ObjectDoesNotExist:
            raise KeyError
        except MultipleObjectsReturned:
            # This should not occur after release as unique together constraint has been added in a migration
            # Covers edge case of duplicate already exists which would cause the unique together migration to fail
            # then this error message will help debug
            logger.error(f"Multiple bundles match '{self.bundle_id}' and organisation '{organisation_name}'"
                         "Error found in channels.py when checking token. A migration added unique together constraint"
                         "which should have prevented this error")
            raise exceptions.AuthenticationFailed('Invalid Token')

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
            return self.looked_up_bundle
        # Bundle will only be looked up when required and only once per request
        if not self.looked_up_bundle:
            try:
                self.looked_up_bundle = ClientApplicationBundle.objects.get(bundle_id=self.bundle_id,
                                                                            client=self.client)
            except ObjectDoesNotExist:
                logger.error(f"No ClientApplicationBundle found for '{self.bundle_id}' and client '{self.client}'"
                             "Bundle id has not been configured to a client in Admin")
                raise exceptions.AuthenticationFailed('Invalid Token')
            except MultipleObjectsReturned:
                logger.error(f"Multiple bundles match '{self.bundle_id}' and client '{self.client}'"
                             "Error found in channels.py when looking up bundle. This a error caused by"
                             "configuring the same bundle to more than one client/organisation.")
                raise exceptions.AuthenticationFailed('Invalid Token')
        return self.looked_up_bundle

    @staticmethod
    def scheme_suspended(relation=''):
        return {f'{relation}schemebundleassociation__status': SchemeBundleAssociation.SUSPENDED}

    def scheme_query(self, query, allow=None):
        return self.related_model_query(query, '', allow)

    def scheme_account_query(self, query, allow=None, user_id=None, user_filter=True):
        if user_filter and not self.service_allow_all:
            query = self._user_filter(query, user_id)
        return self.related_model_query(query, 'scheme__', allow)

    def _user_filter(self, query, user_id):
        if not user_id:
            if self.user:
                user_id = self.user.id
            else:
                raise ValueError("user_id or permit.user is required when filtering by user")
        return query.filter(user_set__id=user_id)

    def scheme_payment_account_query(self, query, allow=None):
        return self.related_model_query(query, 'scheme_account_set__scheme__', allow)

    def payment_card_account_query(self, query, user_id=None, user_filter=True):
        if user_filter and not self.service_allow_all:
            query = self._user_filter(query, user_id)
        return query

    def permit_test_access(self, scheme):
        bundle_assoc = scheme.schemebundleassociation_set.get(bundle=self.bundle)
        not_permitted = not self.user.is_tester and bundle_assoc.test_scheme
        return not not_permitted

    def related_model_query(self, query, relation='', allow=None):
        if self.service_allow_all:
            return query
        bundle_root = f'{relation}schemebundleassociation__'
        status_key = f'{bundle_root}status'
        bundle = {f'{bundle_root}bundle': self.bundle}
        active = {status_key: SchemeBundleAssociation.ACTIVE}
        suspended = {status_key: SchemeBundleAssociation.SUSPENDED}
        not_test_scheme = {f'{bundle_root}test_scheme': False}
        q = Q(**bundle)
        if self.user and not self.user.is_tester:
            q = q & Q(**not_test_scheme)

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
        status_list = SchemeBundleAssociation.get_status_by_bundle_id_and_scheme_id(
            bundle_id=self.bundle_id, scheme_id=scheme_id
        )
        if len(status_list) > 1:
            logger.error(f"Channels id ='{self.bundle_id}' has "
                         f"multiple entries for scheme id '{scheme_id}'")
            raise exceptions.AuthenticationFailed('Invalid Token')

        if status_list:
            status = status_list[0]['status']
        else:
            status = None

        self.found_schemes_status[scheme_id] = status
        if self.ubiquity and status == SchemeBundleAssociation.SUSPENDED:
            status = SchemeBundleAssociation.INACTIVE
        return status
