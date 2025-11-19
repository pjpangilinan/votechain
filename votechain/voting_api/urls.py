from django.urls import path
from . import views

# This file maps URL endpoints to the View functions in views.py

urlpatterns = [
    # --- Pi Terminal Endpoints ---
    # e.g., POST /api/v1/vote/cast
    path('vote/cast', views.CastVoteView.as_view(), name='cast-vote'),

    # e.g., GET /api/v1/election/e-2025-class-president
    path('election/<slug:election_id>', views.PublicElectionDetailView.as_view(), name='public-election-detail'),

    path('register/link-hardware', views.LinkHardwareView.as_view(), name='link-hardware'),

    # --- Public Dashboard Endpoints ---
    # e.g., GET /api/v1/dashboard/e-2025-class-president
    path('dashboard/<slug:election_id>', views.PublicTallyView.as_view(), name='public-tally'),

    path('register/check-id', views.CheckIDView.as_view(), name='check-id'),

    path('register/link-hardware', views.LinkHardwareView.as_view(), name='link-hardware'),
    path('vote/check-status', views.CheckVoterStatusView.as_view(), name='check-voter-status'),

    # --- Admin Endpoints ---
    # e.g., POST /api/v1/admin/elections
    path('admin/elections', views.CreateElectionView.as_view(), name='admin-create-election'),

    path('admin/upload-preapproved-list', views.UploadPreApprovedVotersView.as_view(), name='admin-upload-preapproved'),
]