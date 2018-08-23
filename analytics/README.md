# Intercom → Mnemosyne

This readme outlines the work involved with migrating Hermes from Intercom to Mnemosyne (and therefore using Themis).

All the methods that were being implemented now have a 1-2-1 drop in replacement. This need to be converted over. These are:

| intercom/intercom_api.py                          | mnemosyne/api.py                           |
|---------------------------------------------------|--------------------------------------------|
| `def post_intercom_event(...)`                    | `def post_event(...)`                      |
| `def reset_user_settings(...)`                    | `def reset_user_settings(...)`             |
| `def update_user_custom_attribute(...)`           | `def update_attributes(...)`               |
| `def update_account_status_custom_attribute(...)` | `def update_scheme_account_attribute(...)` |


A helper method has been added which is:

`def update_attribute(...)`

This sits between `update_scheme_account_attribute` and `update_attributes`, but allows for a single attribute to be configured.

## Methods that have been removed


We no longer want payment cards to be updated, therefore the following method has been removed:

`def update_payment_account_custom_attribute(token, account):`

This method was setup for tests related to Intercom integration, therefore isn't being kept around. The new analytics system is also a "fire and forget" setup, so pulling information from Intercom is not supported.

`def get_user_events(token, user_id)`

## MnemosyneException

For now, similar to the existing `IntercomException`, a `MnemosyneException` exists which is thrown if we cannot reach Mnemosyne or if it returns with an error. We need to decide how to proceed with this, since we do not want Intercom to fall out of sync, so a decision needs to be made on how we handle this.