from datetime import datetime
from re import M

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (Footer, Header, Input, Label, ListItem, ListView,
                             Rule, Static)

from components.fields import Fields
from config import CONFIG
from controllers.accounts import get_all_accounts_with_balance
from controllers.persons import create_person, get_all_persons
from models.split import Split
from utils.forms import RecordForm
from utils.validation import validateForm


class ConfirmationModal(ModalScreen):
    def __init__(self, message: str, *args, **kwargs):
        super().__init__(id="confirmation-modal-screen", *args, **kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Container(classes="dialog"):
            yield Label(self.message)

    def on_key(self, event: events.Key):
        if event.key == "enter":
            self.dismiss(True)
        elif event.key == "escape":
            self.dismiss(False)

class ModalContainer(Widget):
    # usage: ModalContainer(w1, w2, w3..... hotkeys=[])
    def __init__(self, *content, hotkeys: list[dict] = []):
        super().__init__(classes="wrapper")
        self.content = content
        self.hotkeys = hotkeys

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(classes="container"):
            for widget in self.content:
                yield widget
        with Container(classes="footer"):
            for hotkey in self.hotkeys:
                key_display = self.app.get_key_display(Binding(hotkey["key"], ""))
                yield Label(f"[bold yellow]{key_display}[/bold yellow] {hotkey['label']}")

class InputModal(ModalScreen):
    def __init__(self, title: str, form: list[dict], *args, **kwargs):
        super().__init__(classes="modal-screen", *args, **kwargs)
        self.title = title
        self.form = form
    
    # def on_mount(self):
    #     self.styles.animate("text_opacity", value=0, duration=0.4)
    
    # --------------- Hooks -------------- #

    def on_key(self, event: events.Key):
        if event.key == "down":
            self.screen.focus_next()
        elif event.key == "up":
            self.screen.focus_previous()
        elif event.key == "enter":
            self.action_submit()
        elif event.key == "escape":
            self.dismiss(None)

    # ------------- Callbacks ------------ #

    def action_submit(self):
        resultForm, errors, isValid = validateForm(self, self.form)
        if isValid:
            self.dismiss(resultForm)
        else: 
            previousErrors = self.query(".error")
            for error in previousErrors:
                error.remove()
            for key, value in errors.items():
                field = self.query_one(f"#row-field-{key}")
                field.mount(Label(value, classes="error"))

    # -------------- Compose ------------- #
    
    def compose(self) -> ComposeResult:
        yield ModalContainer(Fields(self.form))

class TransferModal(ModalScreen):
    def __init__(self, record=None, *args, **kwargs):
        super().__init__(classes="modal-screen", *args, **kwargs)
        self.accounts = get_all_accounts_with_balance()
        self.form = [
            {
                "title": "Label",
                "key": "label",
                "type": "string",
                "placeholder": "Label",
                "isRequired": True,
                "defaultValue": str(record.label) if record else ""
            },
            {
                "title": "Amount",
                "key": "amount",
                "type": "number",
                "placeholder": "0.00",
                "min": 0,
                "isRequired": True,
                "defaultValue": str(record.amount) if record else ""
            },
            {
                "placeholder": "dd (mm) (yy)",
                "title": "Date",
                "key": "date",
                "type": "dateAutoDay",
                "defaultValue": record.date.strftime("%d") if record else datetime.now().strftime("%d")
            }
        ]
        self.fromAccount = record.accountId if record else self.accounts[0].id
        self.toAccount = record.transferToAccountId if record else self.accounts[1].id
        if record:
            self.title = "Edit transfer"
        else:
            self.title = "New transfer"
        self.atAccountList = False
    
    def on_key(self, event: events.Key):
        if self.atAccountList:
            if event.key == "right":
                self.screen.focus_next()
            elif event.key == "left":
                self.screen.focus_previous()
        else:
            if event.key == "up":
                self.screen.focus_previous()
            elif event.key == "down":
                self.screen.focus_next()
        if event.key == "enter":
            self.action_submit()
        elif event.key == "escape":
            self.dismiss(None)
    
    def on_list_view_highlighted(self, event: ListView.Highlighted):
        accountId = event.item.id.split("-")[1]
        if event.list_view.id == "from-accounts":
            self.fromAccount = accountId
        elif event.list_view.id == "to-accounts":
            self.toAccount = accountId
            
    def action_submit(self):
        resultForm, errors, isValid = validateForm(self, self.form)
        if self.fromAccount == self.toAccount:
            self.query_one("#transfer-error").update("From and to accounts cannot be the same")
        else:
            self.query_one("#transfer-error").update("")
            if isValid:
                resultForm["accountId"] = self.fromAccount
                resultForm["transferToAccountId"] = self.toAccount
                resultForm["isTransfer"] = True
                self.dismiss(resultForm)
            else: 
                previousErrors = self.query(".error")
                for error in previousErrors:
                    error.remove()
                for key, value in errors.items():
                    field = self.query_one(f"#row-field-{key}")
                    field.mount(Label(value, classes="error"))
    
    def compose(self) -> ComposeResult:
        yield ModalContainer(
            Container(
                Fields(self.form),
                Container(
                    ListView(
                            *[ListItem(
                                Label(f"{account.name} (Bal: [yellow]{account.balance}[/yellow])", classes="account-name"),
                                    classes="item",
                                    id=f"account-{account.balance}"
                                ) for account in self.accounts]
                            , id="from-accounts", 
                            classes="accounts",
                            initial_index=self.fromAccount - 1
                        ),
                    Label("[italic]-- to ->[/italic]", classes="arrow"),
                    ListView(
                        *[ListItem(
                                Label(f"{account.name} (Bal: [yellow]{account.balance}[/yellow])", classes="account-name"),
                                classes="item",
                                id=f"account-{account.balance}"
                            ) for account in self.accounts]
                            , id="to-accounts",
                            classes="accounts",
                        initial_index=self.toAccount - 1
                    ),
                    id="accounts-container"
                ),
                Label(id="transfer-error"),
                id="transfer-modal"
            )
        )

class RecordModal(InputModal):
    def __init__(self, title: str, form: list[dict] = [], splitForm: list[dict] = [], isEditing: bool = False, *args, **kwargs):
        super().__init__(title, form, *args, **kwargs)
        self.record_form = RecordForm()
        self.splitForm = splitForm
        self.isEditing = isEditing
        self.splitFormOneLength = len(self.record_form.get_split_form(0, False))
        self.splitCount = int(len(splitForm) / self.splitFormOneLength)
        self.persons = get_all_persons()
        self.accounts = get_all_accounts_with_balance()
        self.total_amount = 0
        self.split_total = Label("", id="split-total")
    
    def on_mount(self):
        self._update_split_total()
        if self.splitCount > 0:
            self._update_split_total_visibility(True)
    
    # -------------- Helpers ------------- #
    
    def _get_splits_from_result(self, resultForm: dict):
        splits = []
        for i in range(0, self.splitCount):
            splits.append({
                "personId": resultForm[f"personId-{i}"],
                "amount": resultForm[f"amount-{i}"],
                "isPaid": resultForm[f"isPaid-{i}"],
                "accountId": resultForm[f"accountId-{i}"],
                "paidDate": resultForm[f"paidDate-{i}"]
            })
        return splits

    def _update_split_total(self, update_new: bool = True):
        my_amount = self.query_one("#field-amount").value
        total = float(my_amount) if my_amount else 0
        if update_new:
            for i in range(0, self.splitCount):
                amount = self.query_one(f"#field-amount-{i}").value
                total += float(amount) if amount else 0
        self.total_amount = total
        if self.splitCount > 0:
            self.split_total.update(f"Total amount: [bold yellow]{total:.2f}[/bold yellow]")
    
    def _get_split_widget(self, index: int, fields: list[dict], isPaid: bool):
        return Container(
                Fields(fields),
                Label("Paid", classes="label-paid") if isPaid else Static(),
                id=f"split-{index}",
                classes="split"
            )
    
    def _get_init_split_widgets(self):
        widgets = []
        for i in range(0, self.splitCount):
            oneSplitForm = self.splitForm[i * self.splitFormOneLength: (i + 1) * self.splitFormOneLength]
            # Find the isPaid field in the form fields for this split
            isPaid = False
            for field in oneSplitForm:
                if field.get("id") == f"isPaid-{i}":
                    isPaid = field.get("value", False)
                    break
            widgets.append(self._get_split_widget(i, oneSplitForm, isPaid))
        return widgets
    
    def _update_split_total_visibility(self, mount: bool):
        if mount:
            self.query_one(".container").mount(self.split_total)
        else:
            self.split_total.remove()
    
    # ------------- Callbacks ------------ #
    
    def on_input_changed(self, event: Input.Changed):
        if event.input.id.startswith("field-amount"):
            self._update_split_total()
    
    def on_key(self, event: events.Key):
        match event.key:
            case "down":
                self.screen.focus_next()
            case "up":
                self.screen.focus_previous()
            case "enter":
                self.action_submit()
            case "escape":
                self.dismiss(None)
            case _:
                if not self.isEditing:
                    if event.key == CONFIG.hotkeys.record_modal.new_split:
                        self.action_add_split(paid=False)
                    elif event.key == CONFIG.hotkeys.record_modal.new_paid_split:
                        self.action_add_split(paid=True)
                    elif event.key == CONFIG.hotkeys.record_modal.delete_last_split:
                        self.action_delete_last_split()
    
    def action_add_split(self, paid: bool = False):
        splits_container = self.query_one("#splits-container", Container)
        current_split_index = self.splitCount
        new_split_form_fields = self.record_form.get_split_form(current_split_index, paid)
        for field in new_split_form_fields:
            self.splitForm.append(field)
        splits_container.mount(
            self._get_split_widget(current_split_index, new_split_form_fields, paid)
        )
        # Use call_after_refresh to ensure the mount is complete
        splits_container.call_after_refresh(lambda: self.query_one(f"#field-personId-{current_split_index}").focus())
        self.splitCount += 1
        if self.splitCount == 1:
            self._update_split_total_visibility(True)
            self._update_split_total(update_new=False)

    def action_delete_last_split(self):
        if self.splitCount > 0:
            self.query_one(f"#split-{self.splitCount - 1}").remove()
            for i in range(self.splitFormOneLength):
                self.splitForm.pop()
            self.splitCount -= 1
            if self.splitCount == 0:
                self._update_split_total_visibility(False)

    def action_submit(self):
        # We set the amount field to the total amount for the form to read the value
        input: Input = self.query_one("#field-amount")
        input.__setattr__("heldValue", str(self.total_amount))
        
        resultRecordForm, errors, isValid = validateForm(self, self.form)
        resultSplitForm, errorsSplit, isValidSplit = validateForm(self, self.splitForm)
        if isValid and isValidSplit:
            resultSplits = self._get_splits_from_result(resultSplitForm)
            self.dismiss({
                "record": resultRecordForm,
                "splits": resultSplits
            })
            return 
        previousErrors = self.query(".error")
        # Remove the custom value we set for the field if not valid
        input.__setattr__("heldValue", None)
        for error in previousErrors:
            error.remove()
        for key, value in {**errors, **errorsSplit}.items():
            field = self.query_one(f"#row-field-{key}")
            field.mount(Label(value, classes="error"))

    # -------------- Compose ------------- #

    def compose(self) -> ComposeResult:
        yield ModalContainer(
            Fields(self.form),
            Container(
                *self._get_init_split_widgets(),
                id="splits-container"
            ),
            hotkeys=[
                {"key": CONFIG.hotkeys.record_modal.new_split, "label": "Split amount"},
                {"key": CONFIG.hotkeys.record_modal.new_paid_split, "label": "Split paid"},
                {"key": CONFIG.hotkeys.record_modal.delete_last_split, "label": "Delete split"}
            ] if not self.isEditing else []
        )
