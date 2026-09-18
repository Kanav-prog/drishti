"""
Phase 3: Zone Health Scoring from CAG Report 22 of 2022
Source: Official CAG Performance Audit on Derailments
Gives: Track health + maintenance stress + risk scores by zone
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


@dataclass
class ZoneHealth:
    """Zone health metrics (from CAG audit)"""
    zone_code: str
    zone_name: str
    
    # Track Replacement Cycle (TRC) inspections
    trc_inspections_due: int
    trc_inspections_done: int
    trc_shortfall_pct: float  # Primary risk indicator
    
    # Track machines idling (maintenance stress)
    machines_idle_days_min: int
    machines_idle_days_max: int
    machines_idle_count: int
    
    # Composite risk score (0-100)
    risk_score: int
    
    # SPAD incidents (Signal Passing at Danger)
    spad_incidents: int
    
    def __post_init__(self):
        """Calculate composite score"""
        # Risk = (inspection_shortfall + machine_idle_stress) / 2
        idle_stress = min(100, (sum([self.machines_idle_days_max]) / 100))
        self.risk_score = int((self.trc_shortfall_pct + idle_stress) / 2)


class CAGZoneHealthLoader:
    """Load zone health data from CAG Report 22 of 2022"""

    # CAG Report: Table 2.2.3 (TRC inspection shortfalls by zone)
    # Source: cag.gov.in/webroot/uploads/download_audit_report/2022/Report-No.-22-of-2022_Railway_English_DSC-063a2dda55f3ce6.38649271.pdf
    CAG_ZONE_HEALTH_DATA = [
        {
            'zone_code': 'ER',
            'zone_name': 'Eastern Railway',
            'trc_inspections_due': 482,
            'trc_inspections_done': 424,
            'trc_shortfall_pct': 12,  # (482-424)/482 * 100
            'machines_idle_days_min': 46,
            'machines_idle_days_max': 75,
            'machines_idle_count': 6,
            'spad_incidents': 8,
        },
        {
            'zone_code': 'CR',
            'zone_name': 'Central Railway',
            'trc_inspections_due': 161,
            'trc_inspections_done': 106,
            'trc_shortfall_pct': 38,  # CRITICAL
            'machines_idle_days_min': 21,
            'machines_idle_days_max': 40,
            'machines_idle_count': 4,
            'spad_incidents': 12,
        },
        {
            'zone_code': 'ECR',
            'zone_name': 'East Central Railway',
            'trc_inspections_due': 402,
            'trc_inspections_done': 281,
            'trc_shortfall_pct': 30,  # HIGH
            'machines_idle_days_min': 21,
            'machines_idle_days_max': 123,
            'machines_idle_count': 8,
            'spad_incidents': 15,
        },
        {
            'zone_code': 'NCR',
            'zone_name': 'North Central Railway',
            'trc_inspections_due': 644,
            'trc_inspections_done': 604,
            'trc_shortfall_pct': 6,  # LOW RISK
            'machines_idle_days_min': 24,
            'machines_idle_days_max': 38,
            'machines_idle_count': 2,
            'spad_incidents': 3,
        },
        {
            'zone_code': 'NR',
            'zone_name': 'Northern Railway',
            'trc_inspections_due': 512,
            'trc_inspections_done': 480,
            'trc_shortfall_pct': 6,  # LOW RISK
            'machines_idle_days_min': 12,
            'machines_idle_days_max': 25,
            'machines_idle_count': 1,
            'spad_incidents': 2,
        },
        {
            'zone_code': 'SCR',
            'zone_name': 'South Central Railway',
            'trc_inspections_due': 168,
            'trc_inspections_done': 85,
            'trc_shortfall_pct': 49,  # CRITICAL
            'machines_idle_days_min': 0,
            'machines_idle_days_max': 0,
            'machines_idle_count': 0,
            'spad_incidents': 18,
        },
        {
            'zone_code': 'SER',
            'zone_name': 'South Eastern Railway',
            'trc_inspections_due': 321,
            'trc_inspections_done': 161,
            'trc_shortfall_pct': 50,  # CRITICAL
            'machines_idle_days_min': 16,
            'machines_idle_days_max': 50,
            'machines_idle_count': 5,
            'spad_incidents': 22,
        },
        {
            'zone_code': 'WR',
            'zone_name': 'Western Railway',
            'trc_inspections_due': 169,
            'trc_inspections_done': 74,
            'trc_shortfall_pct': 56,  # CRITICAL
            'machines_idle_days_min': 47,
            'machines_idle_days_max': 73,
            'machines_idle_count': 4,
            'spad_incidents': 25,
        },
        {
            'zone_code': 'NFR',
            'zone_name': 'Northeast Frontier Railway',
            'trc_inspections_due': 83,
            'trc_inspections_done': 56,
            'trc_shortfall_pct': 33,  # HIGH
            'machines_idle_days_min': 0,
            'machines_idle_days_max': 0,
            'machines_idle_count': 0,
            'spad_incidents': 5,
        },
        {
            'zone_code': 'ECoR',
            'zone_name': 'East Coast Railway',
            'trc_inspections_due': 321,
            'trc_inspections_done': 121,
            'trc_shortfall_pct': 62,  # CRITICAL
            'machines_idle_days_min': 206,
            'machines_idle_days_max': 320,
            'machines_idle_count': 8,
            'spad_incidents': 30,
        },
    ]

    def __init__(self):
        self.zones: Dict[str, ZoneHealth] = {}

    def load(self) -> Dict[str, ZoneHealth]:
        """Load CAG zone health data"""
        logger.info("[OSINT] Loading zone health from CAG Report 22 of 2022...")
        
        for data in self.CAG_ZONE_HEALTH_DATA:
            zone = ZoneHealth(
                zone_code=data['zone_code'],
                zone_name=data['zone_name'],
                trc_inspections_due=data['trc_inspections_due'],
                trc_inspections_done=data['trc_inspections_done'],
                trc_shortfall_pct=data['trc_shortfall_pct'],
                machines_idle_days_min=data['machines_idle_days_min'],
                machines_idle_days_max=data['machines_idle_days_max'],
                machines_idle_count=data['machines_idle_count'],
                risk_score=0,  # Will be calculated in __post_init__
                spad_incidents=data['spad_incidents'],
            )
            self.zones[zone.zone_code] = zone
        
        logger.info(f"✅ Loaded {len(self.zones)} zone health records")
        return self.zones

    def get_risk_matrix(self) -> List[Tuple[str, str, int]]:
        """Sort zones by risk (highest first)"""
        return sorted(
            [(z.zone_code, z.zone_name, z.risk_score) for z in self.zones.values()],
            key=lambda x: x[2],
            reverse=True
        )

    def print_zone_health_dashboard(self) -> None:
        """Print zone health as dashboard"""
        logger.info("\n" + "="*100)
        logger.info("ZONE HEALTH DASHBOARD (CAG Report 22 of 2022)")
        logger.info("="*100)
        
        # Risk stratification
        critical = []
        high = []
        medium = []
        low = []
        
        for zone in self.zones.values():
            if zone.risk_score >= 70:
                critical.append(zone)
            elif zone.risk_score >= 50:
                high.append(zone)
            elif zone.risk_score >= 30:
                medium.append(zone)
            else:
                low.append(zone)
        
        # Print by risk level
        logger.info("\n🔴 CRITICAL RISK ZONES (Score >= 70):")
        for zone in critical:
            logger.info(f"  {zone.zone_code:6} {zone.zone_name:40} Score: {zone.risk_score:2} "
                       f"(Inspect shortfall: {zone.trc_shortfall_pct:2}%, SPAD: {zone.spad_incidents})")
        
        logger.info("\n🟠 HIGH RISK ZONES (Score 50-69):")
        for zone in high:
            logger.info(f"  {zone.zone_code:6} {zone.zone_name:40} Score: {zone.risk_score:2} "
                       f"(Inspect shortfall: {zone.trc_shortfall_pct:2}%, SPAD: {zone.spad_incidents})")
        
        logger.info("\n🟡 MEDIUM RISK ZONES (Score 30-49):")
        for zone in medium:
            logger.info(f"  {zone.zone_code:6} {zone.zone_name:40} Score: {zone.risk_score:2} "
                       f"(Inspect shortfall: {zone.trc_shortfall_pct:2}%, SPAD: {zone.spad_incidents})")
        
        logger.info("\n🟢 LOW RISK ZONES (Score < 30):")
        for zone in low:
            logger.info(f"  {zone.zone_code:6} {zone.zone_name:40} Score: {zone.risk_score:2} "
                       f"(Inspect shortfall: {zone.trc_shortfall_pct:2}%, SPAD: {zone.spad_incidents})")
        
        logger.info("\n" + "="*100)
        logger.info("KEY FINDINGS:")
        logger.info(f"  ✅ Low-risk zones: {len(low)}")
        logger.info(f"  ⚠️  Medium-risk zones: {len(medium)}")
        logger.info(f"  🔴 High+Critical zones: {len(high) + len(critical)} (NEED MAINTENANCE)")
        logger.info("="*100 + "\n")

    def get_zone_by_code(self, code: str) -> ZoneHealth | None:
        """Get zone health by code"""
        return self.zones.get(code)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    loader = CAGZoneHealthLoader()
    zones = loader.load()
    
    loader.print_zone_health_dashboard()
    
    risk_matrix = loader.get_risk_matrix()
    print(f"Risk-sorted zones: {risk_matrix}")
