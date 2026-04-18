"""
schema.py
=========
Pydantic models matching Samsung's exact output template from the mentor email.
Every field Samsung asked for is defined here.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ─── Shared primitives ────────────────────────────────────────────────────────

class SingleValue(BaseModel):
    type: str = "single"
    value: Any

class MultiValue(BaseModel):
    type: str = "multi"
    value: List[Any]

BCSField = Union[SingleValue, MultiValue]


# ─── LTE Bands ────────────────────────────────────────────────────────────────

class LTEBandExtras(BaseModel):
    bandEUTRA: Optional[int] = None
    halfDuplex: Optional[bool] = None
    v1250_dl_256QAM_r12: Optional[str] = Field(None, alias="v1250_dl-256QAM-r12")
    v1250_ul_64QAM_r12: Optional[str] = Field(None, alias="v1250_ul-64QAM-r12")
    v9e0_bandEUTRA_v9e0: Optional[str] = Field(None, alias="v9e0_bandEUTRA-v9e0")
    v1320_ue_PowerClass_N_r13: Optional[str] = Field(None, alias="v1320_ue-PowerClass-N-r13")

    class Config:
        populate_by_name = True

class LTEBand(BaseModel):
    band: int
    mimoDl: Optional[SingleValue] = None
    mimoUl: Optional[SingleValue] = None
    modulationDl: Optional[SingleValue] = None
    modulationUl: Optional[SingleValue] = None
    powerClass: Optional[str] = None
    extras: Optional[LTEBandExtras] = None


# ─── NR Bands ─────────────────────────────────────────────────────────────────

class NRBandwidth(BaseModel):
    scs: int
    bandwidthsDl: List[int] = []
    bandwidthsUl: List[int] = []

class NRBandExtras(BaseModel):
    bandNR: Optional[int] = None
    modifiedMPR_Behaviour: Optional[str] = Field(None, alias="modifiedMPR-Behaviour")
    multipleTCI: Optional[str] = None
    pusch_256QAM: Optional[str] = Field(None, alias="pusch-256QAM")
    powerBoosting_pi2BPSK: Optional[str] = Field(None, alias="powerBoosting-pi2BPSK")
    ue_PowerClass_v1610: Optional[str] = Field(None, alias="ue-PowerClass-v1610")
    txDiversity_r16: Optional[str] = Field(None, alias="txDiversity-r16")
    rateMatchingLTE_CRS: Optional[str] = Field(None, alias="rateMatchingLTE-CRS")
    v16c0_pusch_RepetitionTypeA: Optional[str] = Field(None, alias="v16c0_pusch-RepetitionTypeA-v16c0")
    asymmetricBandwidthCombinationSet: Optional[str] = None
    pucch_SpatialRelInfoMAC_CE: Optional[str] = Field(None, alias="pucch-SpatialRelInfoMAC-CE")

    class Config:
        populate_by_name = True

class NRBand(BaseModel):
    band: int
    mimoDl: Optional[SingleValue] = None
    mimoUl: Optional[SingleValue] = None
    modulationDl: Optional[SingleValue] = None
    modulationUl: Optional[SingleValue] = None
    powerClass: Optional[str] = None
    bandwidths: List[NRBandwidth] = []
    rateMatchingLteCrs: Optional[bool] = None
    extras: Optional[NRBandExtras] = None


# ─── LTE CA ───────────────────────────────────────────────────────────────────

class LTECAComponent(BaseModel):
    band: int
    bwClassDl: Optional[str] = None
    bwClassUl: Optional[str] = None
    mimoDl: Optional[SingleValue] = None
    mimoUl: Optional[SingleValue] = None
    modulationDl: Optional[SingleValue] = None
    modulationUl: Optional[SingleValue] = None

class LTECACombo(BaseModel):
    components: List[LTECAComponent] = []
    bcs: Optional[BCSField] = None


# ─── NR CA ────────────────────────────────────────────────────────────────────

class NRCAComponent(BaseModel):
    band: int
    bwClassDl: Optional[str] = None
    bwClassUl: Optional[str] = None
    mimoDl: Optional[SingleValue] = None
    mimoUl: Optional[SingleValue] = None
    modulationDl: Optional[SingleValue] = None
    modulationUl: Optional[SingleValue] = None
    bw90mhzSupported: Optional[bool] = None
    maxScs: Optional[int] = None
    maxBwDl: Optional[SingleValue] = None
    maxBwUl: Optional[SingleValue] = None

class NRCACustomData(BaseModel):
    bandList: Optional[str] = None
    supportedSRS_TxPortSwitch: Optional[str] = Field(None, alias="supportedSRS-TxPortSwitch")
    featureSetCombination: Optional[int] = None
    parallelTxSRS_PUCCH_PUSCH: Optional[str] = Field(None, alias="parallelTxSRS-PUCCH-PUSCH")
    simultaneousRxTxInterBandCA: Optional[str] = None
    diffNumerologyWithinPUCCH_GroupSmallerSCS: Optional[str] = Field(None, alias="diffNumerologyWithinPUCCH-GroupSmallerSCS")
    supportedBandwidthCombinationSet: Optional[str] = None
    powerClass_v1530: Optional[str] = Field(None, alias="powerClass-v1530")
    maxNumberSimultaneousNZP_CSI_RS: Optional[Any] = Field(None, alias="maxNumberSimultaneousNZP-CSI-RS-ActBWP-AllCC")
    totalNumberPortsSimultaneousNZP_CSI_RS: Optional[Any] = Field(None, alias="totalNumberPortsSimultaneousNZP-CSI-RS-ActBWP-AllCC")
    simultaneousCSI_ReportsAllCC: Optional[Any] = None
    supportedNumberTAG: Optional[str] = None
    diffNumerologyWithinPUCCH_GroupLargerSCS: Optional[str] = Field(None, alias="diffNumerologyWithinPUCCH-GroupLargerSCS")

    class Config:
        populate_by_name = True

class NRCACombo(BaseModel):
    components: List[NRCAComponent] = []
    bcs: Optional[BCSField] = None
    customData: List[NRCACustomData] = []


# ─── MRDC ─────────────────────────────────────────────────────────────────────

class MRDCLTEComponent(BaseModel):
    band: int
    bwClassDl: Optional[str] = None
    bwClassUl: Optional[str] = None
    mimoDl: Optional[SingleValue] = None
    mimoUl: Optional[SingleValue] = None
    modulationDl: Optional[SingleValue] = None
    modulationUl: Optional[SingleValue] = None

class MRDCNRComponent(BaseModel):
    band: int
    bwClassDl: Optional[str] = None
    bwClassUl: Optional[str] = None
    mimoDl: Optional[SingleValue] = None
    mimoUl: Optional[SingleValue] = None
    modulationDl: Optional[SingleValue] = None
    modulationUl: Optional[SingleValue] = None
    maxScs: Optional[int] = None
    maxBwDl: Optional[SingleValue] = None
    maxBwUl: Optional[SingleValue] = None

class MRDCCustomData(BaseModel):
    bandList: Optional[str] = None
    featureSetCombination: Optional[int] = None
    dynamicPowerSharingENDC: Optional[str] = None
    simultaneousRxTxInterBandENDC: Optional[str] = None
    powerClass_v1530: Optional[str] = Field(None, alias="powerClass-v1530")
    intraBandENDC_Support: Optional[str] = Field(None, alias="intraBandENDC-Support")
    supportedBandwidthCombinationSetIntraENDC: Optional[str] = None
    supportedBandwidthCombinationSetEUTRA: Optional[str] = Field(None, alias="supportedBandwidthCombinationSetEUTRA-v1530")
    simultaneousRxTxInterBandCA: Optional[str] = None
    supportedBandwidthCombinationSet: Optional[str] = None
    maxNumberSimultaneousNZP_CSI_RS: Optional[Any] = Field(None, alias="maxNumberSimultaneousNZP-CSI-RS-ActBWP-AllCC")
    simultaneousCSI_ReportsAllCC: Optional[Any] = None
    diffNumerologyWithinPUCCH: Optional[str] = Field(None, alias="diffNumerologyWithinPUCCH-GroupSmallerSCS")

    class Config:
        populate_by_name = True

class MRDCCombo(BaseModel):
    componentsLte: List[MRDCLTEComponent] = []
    componentsNr: List[MRDCNRComponent] = []
    bcsNr: Optional[BCSField] = None
    bcsEutra: Optional[BCSField] = None
    customData: List[MRDCCustomData] = []


# ─── Top-level Output ─────────────────────────────────────────────────────────

class Metadata(BaseModel):
    source_file: str = ""
    pkt_version: Optional[str] = None
    rrc_release: Optional[str] = None
    physical_cell_id: Optional[str] = None
    freq: Optional[str] = None
    rat_type: Optional[str] = None
    extraction_method: str = "rule-based"
    confidence: float = 1.0

class SamsungOutput(BaseModel):
    metadata: Metadata = Metadata()
    lteBands: List[LTEBand] = []
    nrBands: List[NRBand] = []
    lteca: List[LTECACombo] = []
    nrca: List[NRCACombo] = []
    mrdc: List[MRDCCombo] = []
