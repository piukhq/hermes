import json
import pickle
from types import SimpleNamespace
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import RetrieveUpdateAPIView, CreateAPIView, UpdateAPIView, ListAPIView, RetrieveAPIView, \
    get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from hermes import settings
from scheme.encyption import AESCipher
from scheme.models import SchemeAccount, Scheme, SchemeCredentialQuestion, SchemeAccountCredentialAnswer
from user.authenticators import UIDAuthentication
from user.models import CustomUser
from user.serializers import UserSerializer, RegisterSerializer, SchemeAccountSerializer


class ForgottenPassword():
    pass


class Login(View):
    @method_decorator(csrf_exempt)
    def post(self, request):
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(email=email, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return HttpResponse(json.dumps({'email': email, 'uid': user.uid}), content_type="application/json")
            else:
                return HttpResponse('The account associated with this email address is suspended.',
                                    content_type="application/json",
                                    status=403)
        else:
            return HttpResponse('Login credentials incorrect.',
                    content_type="application/json",
                    status=403)



# TODO: Could be merged with users
# Will require research, multiple serializers
# Password Handling
class Register(CreateAPIView):
    serializer_class = RegisterSerializer


class ResetPassword(UpdateAPIView):
    pass


class Users(RetrieveUpdateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = CustomUser.objects.all().select_related()
    serializer_class = UserSerializer
    lookup_field = 'uid'


class Authenticate(APIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    @method_decorator(csrf_exempt)
    def get(self, request):
        return HttpResponse(json.dumps({
            'uid': str(request.user.uid),
            'id': str(request.user.id)
        }))


class RetrieveSchemeAccount(RetrieveAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = SchemeAccountSerializer

    def get(self, request, *args, **kwargs):
        scheme = get_object_or_404(Scheme, pk=kwargs['scheme_id'])
        scheme_account = get_object_or_404(SchemeAccount, user=request.user, scheme=kwargs['scheme_id'])
        #     .values('username',
        #             'card_number',
        #             'membership',
        #             'password')
        credentials = {
            'username': scheme_account.username,
            'card_number': scheme_account.card_number,
            'membership_number': scheme_account.membership_number,
            'password': scheme_account.decrypt()
        }
        security_questions = SchemeCredentialQuestion.objects.filter(scheme=scheme)
        if security_questions:
            credentials['extra'] = {}
            for security_question in security_questions:
                answer = SchemeAccountCredentialAnswer.objects.get(scheme_account=scheme_account, question=security_question)
                credentials['extra'][security_question.slug] = answer.decrypt()

        serialized_credentials = json.dumps(credentials)
        encrypted_credentials = AESCipher(settings.AES_KEY.encode()).encrypt(serialized_credentials).decode('utf-8')

        instance = SimpleNamespace(scheme_slug=scheme.slug, credentials=encrypted_credentials)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


