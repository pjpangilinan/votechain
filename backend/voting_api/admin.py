from django.contrib import admin
from .models import Election, Position, Candidate, RegisteredVoter, VoteLedger, PreApprovedVoter


# --- Inline Helpers ---
class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 1


class PositionInline(admin.TabularInline):
    model = Position
    extra = 1
    show_change_link = True


# --- Main Admin Views ---

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'election_id', 'start_date', 'end_date', 'is_active', 'is_open_status')

    readonly_fields = ('election_id',)

    def is_open_status(self, obj):
        return obj.is_open

    is_open_status.boolean = True
    is_open_status.short_description = "Open for Voting?"

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'election', 'max_choices', 'rank')
    list_filter = ('election',)
    inlines = [CandidateInline]


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'party')
    list_filter = ('position__election', 'party')


# --- SECURITY LOCKDOWNS ---

@admin.register(VoteLedger)
class VoteLedgerAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'election', 'current_hash')
    readonly_fields = ('timestamp', 'previous_hash', 'current_hash', 'ballot_data', 'election')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(RegisteredVoter)
class RegisteredVoterAdmin(admin.ModelAdmin):
    list_display = ('election', 'voter_hash', 'has_voted')
    list_filter = ('election', 'has_voted')
    readonly_fields = ('voter_hash', 'has_voted', 'election')

@admin.register(PreApprovedVoter)
class PreApprovedVoterAdmin(admin.ModelAdmin):
    list_display = ('unique_identifier', 'election', 'is_linked')
    list_filter = ('election', 'is_linked')
    search_fields = ('unique_identifier',)
    readonly_fields = ('is_linked',)