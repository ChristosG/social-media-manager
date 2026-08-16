import uuid
import pytest
from app.repo import attachments as att_repo
from app.repo import conversations as conv_repo

pytestmark = pytest.mark.asyncio


async def test_attachment_links_to_message_and_surfaces_in_get_messages(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    a = await att_repo.create_attachment(org, user, "report.pdf", "application/pdf", 2048, "hello text", b"%PDF-1.4")
    conv = await conv_repo.create_conversation(org, user, "New conversation")
    msg_id = await conv_repo.add_message(org, conv["id"], "user", "see attached")
    await att_repo.link_to_message(org, msg_id, [a["id"]])

    msgs = await conv_repo.get_messages(org, conv["id"])
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert len(user_msg["attachments"]) == 1
    att = user_msg["attachments"][0]
    assert att["id"] == a["id"]
    assert att["original_filename"] == "report.pdf"      # UI field mirrored from filename
    assert att["mime_type"] == "application/pdf"
    assert att["file_size"] == 2048


async def test_link_does_not_rehome_an_already_linked_attachment(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    a = await att_repo.create_attachment(org, user, "a.txt", "text/plain", 5, "x", b"x")
    conv = await conv_repo.create_conversation(org, user, "c")
    m1 = await conv_repo.add_message(org, conv["id"], "user", "first")
    m2 = await conv_repo.add_message(org, conv["id"], "user", "second")
    await att_repo.link_to_message(org, m1, [a["id"]])
    await att_repo.link_to_message(org, m2, [a["id"]])  # must be a no-op (already linked)

    msgs = await conv_repo.get_messages(org, conv["id"])
    by_id = {m["id"]: m for m in msgs}
    assert len(by_id[m1]["attachments"]) == 1
    assert by_id[m2]["attachments"] == []


async def test_messages_without_attachments_return_empty_list(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    conv = await conv_repo.create_conversation(org, user, "c")
    await conv_repo.add_message(org, conv["id"], "user", "no files here")
    msgs = await conv_repo.get_messages(org, conv["id"])
    assert msgs[0]["attachments"] == []
