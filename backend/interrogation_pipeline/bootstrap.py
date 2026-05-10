"""First-boot seeding: insert all four pipelines' channels.

Idempotent — re-running has no effect because channels.id is the PK.

Channel-priority dedup rule (handoff §4.5): if a channel appears in multiple
pipeline lists, the higher-priority pipeline wins. Priority order is
P4 > P3 > P1 > P2. Lower-priority duplicates are skipped at seed time.

P2 is seeded `active=False` because the handoff explicitly marks it DORMANT.
The user can flip channels on individually from the Channels page.
"""

from __future__ import annotations

from interrogation_pipeline.config.settings import settings
from interrogation_pipeline.discovery.rss import rss_url_for
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import ChannelRepo


# Format: (channel_id_or_handle, display_name, since_iso)
# since_iso is None for "all videos" (full lifetime scrape).

P4_CHANNELS: list[tuple[str, str, str | None]] = [
    ("@MidwestSafety", "Midwest Safety", None),
    ("@ThreeeRedddInterrogations", "Three Redd Interrogations", None),
    ("@TheCrimeSeen", "The Crime Seen", None),
    ("UCwpR58QA4tNpTKMeLsP6oIQ", "Channel UCwpR58…", None),
    ("@BloodlinesCrime", "Bloodlines Crime", None),
    ("@DamonVerial", "Damon Verial", None),
    ("@FirstDegreeCrime", "First Degree Crime", None),
    ("@TheyCAUGHTme", "They CAUGHT Me", None),
    ("@BloodlineInterrogations", "Bloodline Interrogations", None),
    ("@DeepCaseInterrogations", "Deep Case Interrogations", None),
    ("@DeadliestHours", "Deadliest Hours", None),
    ("@RedBearInterrogations", "Red Bear Interrogations", None),
    ("@LawAndCrime", "Law & Crime", "2026-04-07T00:00:00+00:00"),
]

P3_CHANNELS: list[tuple[str, str, str | None]] = [
    ("@lawandcrimebodycam", "Law & Crime Bodycam", None),
    ("@lawandcrimetrials", "Law & Crime Trials", "2026-04-15T00:00:00+00:00"),
    ("@LawAndCrimeInvestigates", "Law & Crime Investigates", None),
    ("@BestOfLawAndCrime", "Best Of Law & Crime", None),
]

P1_CHANNELS: list[tuple[str, str, str | None]] = [
    ("UCNpjH9MosivtBOa45Hbu39g", "Red File", None),
    ("UC7_MOIpN8fn_UZAivnn10_Q", "M7 Crime Storytime", None),
    ("UCEFZXQj2c4oJtXfKRdl3CBA", "Channel UCEFZXQ…", None),
    ("UCF7evaQSDbm7vqFa459zi-g", "Channel UCF7eva…", None),
    ("UC0hPh-s57PdU215UJglALCw", "Channel UC0hPh…", None),
    ("UCAAylaLTtNL8SGuB-Oj3xCw", "Channel UCAAyla…", None),
    ("UCtbdyi6xVsQVUA2IuiTtM2g", "Channel UCtbdyi…", None),
    ("UCdM8IVdAmETWGfAf4TuSpHQ", "Channel UCdM8IV…", None),
    ("UCYdbEnexYsUw-bv0kkJC2EA", "Channel UCYdbEn…", None),
    ("UC2oyGvGVpag7aRvEbvFGw3g", "Channel UC2oyGv…", None),
    ("UCbW-Cu6lcOrW3g5e2rdyLNw", "Channel UCbW-Cu…", None),
    ("UC2Bz8MkHXZgCdi6voGQ0v0Q", "Channel UC2Bz8M…", None),
    ("UCRJK1_ZvsdqmGmz4pYYlFTQ", "Channel UCRJK1_…", None),
    ("UCVXKabRhXSQXh_U0au5JSzQ", "Channel UCVXKab…", None),
    ("UCJWKjrrUh2KL1d3zXQW79cQ", "Channel UCJWKjr…", None),
    ("UCjnYCUIym8wNRjLtZCc6gNg", "Channel UCjnYCU…", None),
    ("@EWUBodycam", "EWU Bodycam", None),
    ("@ExploreWithUs", "Explore With Us", None),
    ("@EWUCrimeStorytime", "EWU Crime Storytime", None),
    ("@EWUCrew", "EWU Crew", None),
    ("@EWUUnsolved", "EWU Unsolved", None),
    ("@TheVillainsCrime", "The Villains Crime", None),
    ("@TheDecoderProduction", "The Decoder Production", None),
    ("@DangleCrime", "Dangle Crime", None),
    ("@Crime-Cracked", "Crime Cracked", None),
    ("@CodeC911", "Code C911", None),
    ("@intheroom-crime", "In The Room Crime", None),
    ("@7newsspotlight", "7 News Spotlight", None),
    ("@redcircleinterrogationsand5722", "Red Circle Interrogations", None),
    ("@itspoliceprime", "It's Police Prime", None),
]

# P2 is large (104 channels) and DORMANT; seeded inactive.
P2_CHANNELS: list[tuple[str, str, str | None]] = [
    ("@thingspolicesee", "Things Police See", "2026-04-06T00:00:00+00:00"),
    ("@streetcoptraining7978", "Street Cop Training", "2026-04-06T00:00:00+00:00"),
    ("UCk7axbdyPf_Pn3SJorC5WIA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCH7C3dU5ydIDCKbjHbNGcRw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCarYTcD_WfwI-MkIgqTKbWA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCADO7MK9B08sBEgXK2eH_Gw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCOzUXFP7J2k8zf3KN8ms6-A", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCyVDZzuRMWcn3wbaBOrcgXA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCPE9ydGjoZBbUUe7pfhClgQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCCpb8o_jAirEAuUElKGkajA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCnIYeQdSJ9j3WrAGyBUS5OA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCh8m4wSh0ijQoe0NRo-cSuA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCm-5L6K2UAR0hfRTRpOJpjQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCZZzGcYQ98S9camwigO2-rQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCJvQzsTmZFZgyewjJWDh2Eg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC8Zu5Y2dpHFyVAfK0J1Dx5A", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCHb-gPG8N_G1PF3S8RlWLDQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC8RRSvUJBIE3ZwRiIDJ5WCQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UClTO_YUEIMY_h4Vmnw1eSGg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UChXXE1zDwAb28LovDo4FuPw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCVw-tphLYD9l0SsUtKIlE9g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCuiIwb6mOJVm1rSgnbbKkXQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC08025ctvyJFFnluyv7k1OQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCPCOWnKkD1VqE4n_8TznaoA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCCIB1RGsT1LeAcuLfEidrUA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC-3fsTpAH4LhWJrb89bMOlw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCJaHwLPBI-o1NuYh-GlCJoA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCs2mVuZgKhWSuNPT565RNIA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCC83luL_D7q2C9AGVtnCMPA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCXsBznpYSWvIKkfIib-Sqtw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCfJsOa7m1zKMS9T2dvIljfQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCCKkuXux09y-TCg-BQxCjNA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCwwE3Wf6I4OI0yizs26NvUQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCwNEHTjIuIdZbjWPfsNGqFA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCi9LaoY3GbqCdbbRyaQ5_vA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC0Xe--tV7PTSI-ZnEbiAwUA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCWvJOeZa-YPpVwa_151Kewg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCpgGspoawKG9V4kpcZj1mvQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCPlH2h2Ckq1T-DKqw0latYA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCL2PEbBDdK3KPUUSn55DASg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCJUhyzJSM9J4QYC_m69TFnw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCGbxXA5-fSCMTH44PA-SLWg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCgG28RTH48Imf8feEUycW8A", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCRmnt09hfWo6hD574tLVVDQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UChf3UCRLbu6n16wmqtKhs3w", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UChyWZOoi1YAz6RoLSdzdl8A", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCGS_OKZwBraNQGAduRxJ0ug", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCbFiRhonZXRq0SWT9BLhURg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCuobtuGxJny9V5lX5a1ieuw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCcjq_zNPiCrXc94clo3C7Lg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCeQaMosfbo2Y8x3AFXB_aRQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC_gw-r1bA266U0mlddXJ4jA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UClpN1KGwKTTbnCNBdqL5pfQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCUo1afaRkB6BWajMMH6ZFkA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCH8688NYs4zdEALBE6-LUhQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC70WjigkEG7CGDEPGFJcspg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC7jApVmMdNftb6q8LnCdxUQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC-yNP6SYb5bSt5S6Awq7oqw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCO4VzMiL_ZpDH1HGOjWtvaQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCaqe8FwSxvplg5sp_tdI3fQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCW8Oog9pSV5i4pC4aEB50dw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCdBzG30oquDiUitXznndsBA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCzs0PJGuCHWXU0vLsP3ImnQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC1K1yGOMePEQJplM3jU1epA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCndCO7DG4j7V9np7Wk2Dkew", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCMapMoRko-TMBjXBW9yBusw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCv0m1hbV1lZn-UB3kWndsEg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCc-0YpRpqgA5lPTpSQ5uo-Q", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC3gCAgSxWQ6gncurTrs0KfQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCHcZfvZsje29e-yx6LFHN1g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCqqxsLlUJVkvN6NcL8-umcg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCJ8-AAk1WYdrRZPQbSzYenA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCcbYGghMnAxdhICVPaXoxVw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCJke77BZGbcl0dq0nvPgr9g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCZA4nduTtC076VBLJUAZTGQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCjY7230zpHS9Rhu6HVBMPVg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC4cai_IceI3e7iSJFrSXLxQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCR978e9_R5UTNASF9C9AVgw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCDMTDUZQk8VSgShniLLwgmA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCWE96-Cbm-0522aCI6799gA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCDwPFtfvmEcMfAFVddx6T6g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCY2gu_sXDEAyf4RgK2Qz3_g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC9iApPMqx79KpOnXPZD-DqQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC8Jy4v1vnwHNL10fyoXhUGw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCTzQT_DlbkVhXf6iSiZWlbw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCrOKDAUB-iL2wLzZdRN7xgA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCZtPAQuWP8OcfdciXE0G04g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCogWaeVistjvcF33VIWVFMQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCB_LtFE3UDcNwMa-W_I54MQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCQ8pUKyVLrrx4AnXsdgyTVA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCKWaQqOrHIMf51dspBd__1w", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC1Q4fKuozcI5yqyjkSWqBfw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCqGVRafLmxXbOjKEx-S4bfA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UC1oS_xR3f_bOe013bDPaFCw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCG9UwBUQWrVahozYt1PKcLg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCRBPAf6aWmoULJDABGhRqdg", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCQLxT-gl_u3KDuexkEGLOkw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCGBZFFufYgUJ56MCvfyAXfA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCTPteN1e-9MYr0lmyx1ApKA", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCMV3pzWIhJGLYzoHyxBjjNw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCQFvmd1tcYe4ZIw-Bqf3aLw", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCXMYxKMh3prxnM_4kYZuB3g", "P2 channel", "2026-04-13T00:00:00+00:00"),
    ("UCazRf1jcMNZEL1MS5i_rWQQ", "P2 channel", "2026-04-13T00:00:00+00:00"),
    # @lawandcrimetrials in xlsx P2 — skipped (lives in P3 by priority rule).
]


# Ordered by priority (highest first). Channel ID dedup walks this order.
PIPELINE_LISTS: list[tuple[str, list[tuple[str, str, str | None]], bool]] = [
    ("P4", P4_CHANNELS, True),
    ("P3", P3_CHANNELS, True),
    ("P1", P1_CHANNELS, True),
    ("P2", P2_CHANNELS, False),  # DORMANT — seeded inactive
]


async def seed_all_channels() -> dict[str, int]:
    """Seed channels from all four pipelines, applying P4 > P3 > P1 > P2 priority."""
    inserted = {"P4": 0, "P3": 0, "P1": 0, "P2": 0}
    seen: set[str] = set()

    async with session_scope() as session:
        repo = ChannelRepo(session)
        existing = {c.id for c in await repo.list_all()}
        seen.update(existing)

        for pipeline, channels, default_active in PIPELINE_LISTS:
            cookies = str(settings.cookies_dir / f"cookies_{pipeline.lower()}.txt")
            for cid, name, since in channels:
                if cid in seen:
                    continue
                await repo.upsert(
                    id=cid,
                    display_name=name,
                    pipeline=pipeline,
                    rss_url=rss_url_for(cid),
                    since_iso=since,
                    cookies_path=cookies,
                    active=default_active,
                )
                seen.add(cid)
                inserted[pipeline] += 1

    return inserted


# Backwards-compat alias for the previous bootstrap function name.
seed_p4_channels = seed_all_channels
