"""
Main GraphQL Schema for SkillForge Django
"""
import graphene
from graphene_django import DjangoObjectType
from accounts.models import Account
from members.models import Member


# Object Types
class AccountType(DjangoObjectType):
    class Meta:
        model = Account
        fields = '__all__'


class MemberType(DjangoObjectType):
    age = graphene.Int()

    class Meta:
        model = Member
        fields = '__all__'

    def resolve_age(self, info):
        return self.age


# Queries
class Query(graphene.ObjectType):
    # Account queries
    all_accounts = graphene.List(AccountType)
    account = graphene.Field(AccountType, account_id=graphene.UUID(required=True))

    # Member queries
    all_members = graphene.List(MemberType)
    member = graphene.Field(MemberType, member_id=graphene.UUID(required=True))
    members_by_account = graphene.List(MemberType, account_id=graphene.UUID(required=True))

    def resolve_all_accounts(root, info):
        return Account.objects.all()

    def resolve_account(root, info, account_id):
        try:
            return Account.objects.get(account_id=account_id)
        except Account.DoesNotExist:
            return None

    def resolve_all_members(root, info):
        return Member.objects.all()

    def resolve_member(root, info, member_id):
        try:
            return Member.objects.get(member_id=member_id)
        except Member.DoesNotExist:
            return None

    def resolve_members_by_account(root, info, account_id):
        return Member.objects.filter(account_id=account_id)


# Mutations
class CreateAccount(graphene.Mutation):
    class Arguments:
        account_type = graphene.String(required=True)
        subscription_tier = graphene.String()
        max_members = graphene.Int()

    account = graphene.Field(AccountType)

    @staticmethod
    def mutate(root, info, account_type, subscription_tier=None, max_members=1):
        account = Account(
            account_type=account_type,
            subscription_tier=subscription_tier,
            max_members=max_members
        )
        account.save()
        return CreateAccount(account=account)


class CreateMember(graphene.Mutation):
    class Arguments:
        account_id = graphene.UUID(required=True)
        display_name = graphene.String(required=True)
        email = graphene.String()
        date_of_birth = graphene.Date(required=True)
        role = graphene.String(required=True)

    member = graphene.Field(MemberType)

    @staticmethod
    def mutate(root, info, account_id, display_name, date_of_birth, role, email=None):
        member = Member(
            account_id=account_id,
            display_name=display_name,
            email=email,
            date_of_birth=date_of_birth,
            role=role
        )
        member.save()
        return CreateMember(member=member)


class Mutation(graphene.ObjectType):
    create_account = CreateAccount.Field()
    create_member = CreateMember.Field()


# Schema
schema = graphene.Schema(query=Query, mutation=Mutation)
