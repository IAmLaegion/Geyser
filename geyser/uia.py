"""Thin wrapper over the Windows UI Automation COM API.

Each Automation instance lives on one thread (the scanner thread) in a multithreaded apartment.
Buttons are found with a single conditioned FindAll, so the target app's accessibility provider
does the filtering instead of Python walking hundreds of elements.
"""
import gc

import comtypes
import comtypes.client
from comtypes import COMError

UIA_InvokePatternId = 10000
UIA_LegacyIAccessiblePatternId = 10018
UIA_ControlTypePropertyId = 30003
UIA_NamePropertyId = 30005
UIA_ButtonControlTypeId = 50000
UIA_HyperlinkControlTypeId = 50005
UIA_TextControlTypeId = 50020
TreeScope_Descendants = 4
PropertyConditionFlags_IgnoreCase = 1


def _client_module():
    try:
        from comtypes.gen import UIAutomationClient

        return UIAutomationClient
    except ImportError:
        return comtypes.client.GetModule("UIAutomationCore.dll")


class Match:
    __slots__ = ("element", "name", "runtime_id")

    def __init__(self, element, name, runtime_id):
        self.element = element
        self.name = name
        self.runtime_id = runtime_id


RPC_E_CHANGED_MODE = -2147417850


class Automation:
    def __init__(self):
        # If something already initialised COM on this thread in another mode, use that apartment
        # rather than failing. UI Automation works in either; we don't subscribe to UIA events.
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
            self._owns_com = True
        except OSError as exc:
            if getattr(exc, "winerror", None) != RPC_E_CHANGED_MODE:
                raise
            self._owns_com = False
        try:
            self._mod = _client_module()
            self._uia = comtypes.client.CreateObject(self._mod.CUIAutomation, interface=self._mod.IUIAutomation)
            self._text_cond = self._uia.CreatePropertyCondition(UIA_ControlTypePropertyId, UIA_TextControlTypeId)
        except Exception:
            if self._owns_com:
                comtypes.CoUninitialize()
            raise
        self._button_key = None
        self._button_cond = None

    def close(self):
        self._button_cond = self._text_cond = self._uia = None
        gc.collect()
        if self._owns_com:
            comtypes.CoUninitialize()

    def _button_condition(self, texts):
        key = tuple(texts)
        if key != self._button_key:
            uia = self._uia
            types = uia.CreateOrCondition(
                uia.CreatePropertyCondition(UIA_ControlTypePropertyId, UIA_ButtonControlTypeId),
                uia.CreatePropertyCondition(UIA_ControlTypePropertyId, UIA_HyperlinkControlTypeId),
            )
            names = None
            for text in texts:
                cond = uia.CreatePropertyConditionEx(UIA_NamePropertyId, text, PropertyConditionFlags_IgnoreCase)
                names = cond if names is None else uia.CreateOrCondition(names, cond)
            self._button_cond = uia.CreateAndCondition(types, names)
            self._button_key = key
        return self._button_cond

    def find_buttons(self, hwnd, texts):
        root = self._uia.ElementFromHandle(hwnd)
        found = root.FindAll(TreeScope_Descendants, self._button_condition(texts))
        matches = []
        if not found:
            return matches
        for i in range(found.Length):
            el = found.GetElement(i)
            try:
                rect = el.CurrentBoundingRectangle
                # Collapsed menus and templates report an all-zero rectangle; they aren't really on the page.
                if rect.left == rect.top == rect.right == rect.bottom == 0:
                    continue
                matches.append(Match(el, (el.CurrentName or "").strip(), tuple(el.GetRuntimeId() or ())))
            except COMError:
                continue
        return matches

    def invoke(self, element) -> str:
        """Clicks through accessibility actions only. Never moves the mouse."""
        try:
            pattern = element.GetCurrentPattern(UIA_InvokePatternId)
            if pattern:
                pattern.QueryInterface(self._mod.IUIAutomationInvokePattern).Invoke()
                return "invoke"
        except COMError:
            pass
        pattern = element.GetCurrentPattern(UIA_LegacyIAccessiblePatternId)
        if pattern:
            pattern.QueryInterface(self._mod.IUIAutomationLegacyIAccessiblePattern).DoDefaultAction()
            return "default action"
        raise RuntimeError("the button exposes no click action")

    def texts_under(self, hwnd):
        root = self._uia.ElementFromHandle(hwnd)
        found = root.FindAll(TreeScope_Descendants, self._text_cond)
        texts = []
        if not found:
            return texts
        for i in range(found.Length):
            try:
                texts.append(found.GetElement(i).CurrentName or "")
            except COMError:
                continue
        return texts
