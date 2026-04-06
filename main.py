import pygame
import sys
import math
import random
from collections import deque

# =============== FYSIKKONSTANTER ===============
R_GAS = 287.05  # J/(kg*K)
C_V = 718.0     # J/(kg*K)
C_P = 1005.0    # J/(kg*K)
GAMMA = C_P / C_V
P_ATM = 101325.0 # Pa
T_ATM = 293.15   # K

def flow_function(p_up, p_down):
    """Beräknar flödesfunktionen (Psi) för kompressibel gas"""
    if p_up <= 0: return 0.0
    pr = p_down / p_up
    if pr >= 1.0: return 0.0
    pr = max(pr, 0.001)
    
    # Kritisk tryckkvot
    pr_crit = (2.0 / (GAMMA + 1.0)) ** (GAMMA / (GAMMA - 1.0))
    if pr < pr_crit:
        pr = pr_crit
        
    term = (pr ** (2.0 / GAMMA)) - (pr ** ((GAMMA + 1.0) / GAMMA))
    return math.sqrt(abs(2.0 * GAMMA / (GAMMA - 1.0) * max(0, term)) + 1e-9)

def mass_flow(C_d, A, p_up, T_up, p_down):
    """Massflödesberäkning (kg/s) genom en area A"""
    if p_up <= p_down or A <= 0: return 0.0
    psi = flow_function(p_up, p_down)
    return C_d * A * p_up / math.sqrt(R_GAS * max(1.0, T_up)) * psi

class EnginePhysics:
    def __init__(self):
        # Geometri (meter)
        self.B = 0.054      # Borrning (54 mm)
        self.R = 0.025      # Slaglängd/2 (25 mm) -> Slag 50mm
        self.L = 0.095      # Vevstake (95 mm)
        self.A_p = math.pi * (self.B / 2)**2
        self.V_d = self.A_p * 2 * self.R
        
        self.V_c = self.V_d / 8.5  # Förbränningsrum (Kompression ~ 9.5:1)
        self.V_cr_min = self.V_d * 1.8 # Vevhus min-volym
        
        # Dynamik
        self.I_engine = 0.015 # Tröghetsmoment kg*m^2
        self.friction = 0.8   # Grundfriktion Nm
        
        # Portar (avstånd från TDC i meter)
        self.x_exh = 0.024  # Avgasport öppnar (24mm från TDC)
        self.x_tr = 0.034   # Överströmning öppnar (34mm från TDC)
        self.w_exh = 0.038  # Avgasport bredd (båg-längd)
        self.w_tr = 0.032   # Överströmning bredd
        self.A_in_max = 0.0012 # Reedventil max area
        
        # Tillstånd
        self.theta = 0.0      
        self.omega = 150.0    # ca 1400 rpm (tomgång)
        
        # Termodynamiska tillstånd
        self.m_cyl = self.V_c * P_ATM / (R_GAS * T_ATM)
        self.T_cyl = T_ATM
        self.m_cr = self.V_cr_min * P_ATM / (R_GAS * T_ATM)
        self.T_cr = T_ATM
        
        self.x_b_cyl = 0.0 # Bränd gasandel (0 = fräsch, 1 = avgas)
        
        # Tändning och förbränning (Wiebe)
        self.ignition_angle_deg = 340 # 20 f.Ö.D
        self.combustion_active = False
        self.theta_ign = 0.0
        self.m_fuel = 0.0
        
        self.throttle = 1.0
        self.spark_active = False

    def get_kinematics(self, theta):
        """Exakt slider-crank kinematik"""
        s_theta = math.sin(theta)
        c_theta = math.cos(theta)
        beta = math.asin(self.R / self.L * s_theta)
        c_beta = math.cos(beta)
        
        # x = position från TDC (neråt)
        x = self.R + self.L - (self.R * c_theta + self.L * c_beta)
        
        # dx/dtheta för hastighet och volymförändring
        dx_dtheta = self.R * s_theta * (1 + self.R * c_theta / (self.L * c_beta))
        
        V_cyl = self.V_c + self.A_p * x
        V_cr = self.V_cr_min + self.A_p * (2*self.R - x)
        
        return x, V_cyl, V_cr, dx_dtheta
        
    def step(self, dt):
        # Begränsa dt för stabilitet i Euler-integrationen
        if dt > 0.01: dt = 0.01
        
        x, V_cyl, V_cr, dx_dtheta = self.get_kinematics(self.theta)
        
        # Ideala gaslagen
        p_cyl = self.m_cyl * R_GAS * self.T_cyl / V_cyl
        p_cr = self.m_cr * R_GAS * self.T_cr / V_cr
        
        # Fysiska öppningsareor baserat på kolvposition
        A_exh = max(0.0, x - self.x_exh) * self.w_exh
        A_tr = max(0.0, x - self.x_tr) * self.w_tr
        A_in = self.A_in_max * self.throttle if p_cr < P_ATM else 0.0  # Förenklad reed-ventil
        
        # Massflöden (kg/s)
        dm_exh = mass_flow(0.7, A_exh, p_cyl, self.T_cyl, P_ATM) if p_cyl > P_ATM else -mass_flow(0.7, A_exh, P_ATM, T_ATM, p_cyl)
        dm_tr = mass_flow(0.7, A_tr, p_cr, self.T_cr, p_cyl) if p_cr > p_cyl else -mass_flow(0.7, A_tr, p_cyl, self.T_cyl, p_cr)
        dm_in = mass_flow(0.6, A_in, P_ATM, T_ATM, p_cr) if P_ATM > p_cr else 0.0
            
        # Uppdatera massor
        self.m_cyl += (dm_tr - dm_exh) * dt
        self.m_cr += (dm_in - dm_tr) * dt
        
        # Energi / Temperatur i vevhus
        dV_cyl = self.A_p * dx_dtheta * self.omega * dt
        dV_cr = -self.A_p * dx_dtheta * self.omega * dt
        
        dU_cr = P_ATM * dm_in * C_P - (self.T_cr * C_P) * max(0, dm_tr) + (self.T_cyl * C_P) * max(0, -dm_tr) - p_cr * dV_cr
        self.T_cr = max(T_ATM, self.T_cr + dU_cr / (self.m_cr * C_V + 1e-6))
        
        # Tändning
        self.spark_active = False
        theta_deg = math.degrees(self.theta) % 360
        if 0 <= self.angle_diff(theta_deg, self.ignition_angle_deg) < 15 and not self.combustion_active and x < 0.02:
            self.combustion_active = True
            self.spark_active = True
            self.theta_ign = self.theta
            # Bränsle baserat på fräsch luftmassa (ca AFR 14:1 men förenklat)
            self.m_fuel = self.m_cyl * 0.06 * max(0, 1 - self.x_b_cyl)
                
        # Förbränning (Förenklad Wiebe)
        dQ_comb = 0.0
        if self.combustion_active:
            dtheta = (self.theta - self.theta_ign) % (2*math.pi)
            duration = math.radians(45) # Brinntid i vevgrader
            if dtheta < duration:
                Q_total = self.m_fuel * 44e6 # 44 MJ/kg för bensin
                dQ_comb = (Q_total / duration) * (abs(self.omega) * dt + 1e-6)
                self.x_b_cyl += (abs(self.omega) * dt) / duration
                if self.x_b_cyl > 1.0: self.x_b_cyl = 1.0
            else:
                self.combustion_active = False
                
        # Scavenging: Inkommande fräsch gas från överströmning sänker avgasandelen
        if A_tr > 0 and dm_tr > 0:
            added = dm_tr * dt
            self.x_b_cyl = max(0.0, self.x_b_cyl * (self.m_cyl - added) / (self.m_cyl + 1e-6))
            
        # Energi / Temperatur i cylinder
        dU_cyl = dQ_comb + (self.T_cr * C_P) * max(0, dm_tr) - (self.T_cyl * C_P) * max(0, dm_exh) - p_cyl * dV_cyl
        self.T_cyl = max(T_ATM, self.T_cyl + dU_cyl / (self.m_cyl * C_V + 1e-6))
        
        # Newtonsk kylning mot väggarna
        self.T_cyl -= (self.T_cyl - 350) * 15.0 * dt
        self.T_cr -= (self.T_cr - 300) * 5.0 * dt
        
        # Begränsa temperaturer för att undvika instabilitet
        self.T_cyl = min(self.T_cyl, 3000.0)
        self.T_cr = min(self.T_cr, 500.0)
        
        # Vridmomentberäkning
        F_gas = (p_cyl - P_ATM) * self.A_p
        F_cr = (p_cr - P_ATM) * self.A_p
        # Hävstång multiplicerat med nettokraften ger vridmoment
        torque = (F_gas - F_cr) * dx_dtheta
        
        # Friktion och tröghet
        net_torque = torque - self.friction - self.omega * 0.015
        
        self.omega += (net_torque / self.I_engine) * dt
        
        # Simulera en enkel tomgångsmotor / startmotor
        if self.omega < 50.0: 
            self.omega += (150.0 - self.omega) * 5.0 * dt
            
        # Förhindra extrem varvning (NaN-skydd)
        self.omega = max(-1000.0, min(self.omega, 1500.0))
            
        self.theta = (self.theta + self.omega * dt) % (2*math.pi)
        
        return {
            'x': x, 'p_cyl': p_cyl, 'p_cr': p_cr, 'A_exh': A_exh, 'A_tr': A_tr, 'A_in': A_in,
            'rpm': self.omega * 30 / math.pi, 'torque': torque, 'dm_exh': dm_exh, 'dm_tr': dm_tr, 'dm_in': dm_in
        }

    def angle_diff(self, a, b):
        return (a - b + 180) % 360 - 180

# =============== PYGAME SETUP & RENDERING ===============
WIDTH, HEIGHT = 1300, 720
FPS = 60
BG_COLOR = (15, 15, 25)
CYL_COLOR = (180, 180, 210, 100)
PISTON_COLOR = (120, 120, 140)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Realistisk 2-taktsmotor - Exakt Termodynamik & Gasdynamik")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 18)
small_font = pygame.font.SysFont("consolas", 14)

engine = EnginePhysics()

# Visuella skalor (för att mappa meter till pixlar)
SCALE = 3000 # pixlar per meter
CRANK_X = 400
CRANK_Y = 550
# Cylinderns y-koordinat kalibreras så att TDC (x=0) mappar korrekt
CYL_Y = CRANK_Y - (engine.R + engine.L) * SCALE 

class Particle:
    def __init__(self, x, y, color, vx, vy, fade_speed=8):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.life = 255
        self.size = random.uniform(2, 4.5)
        self.fade_speed = fade_speed

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.fade_speed
        
    def draw(self, surf):
        if self.life > 0:
            c = (*self.color, int(self.life))
            pygame.draw.circle(surf, c, (int(self.x), int(self.y)), int(self.size))

particles = []
pv_cyl_points = deque(maxlen=300)
pv_cr_points = deque(maxlen=300)

running = True
paused = False
slow_mo = 1.0

# Fysik-substeps för stabilitet vid höga tryckspikar (explicit Euler kan bli instabil)
SUBSTEPS = 10

while running:
    raw_dt = clock.tick(FPS) / 1000.0 * slow_mo
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: engine.throttle = min(1.0, engine.throttle + 0.25)
            if event.key == pygame.K_DOWN: engine.throttle = max(0.0, engine.throttle - 0.25)
            if event.key == pygame.K_p: paused = not paused
            if event.key == pygame.K_s: slow_mo = 0.1 if slow_mo > 0.5 else 1.0
            
    if not paused:
        dt = raw_dt / SUBSTEPS
        for _ in range(SUBSTEPS):
            state = engine.step(dt)
            
            # Skapa partiklar inuti fysikloopen för exakt timing
            if state['dm_exh'] > 0 and random.random() < state['dm_exh'] * dt * 20000:
                exh_y = CYL_Y + engine.x_exh * SCALE + 10
                particles.append(Particle(CRANK_X + engine.B/2*SCALE, exh_y + random.uniform(0, 20), (120, 120, 120), random.uniform(5, 12), random.uniform(-1, 1)))
                
            if state['dm_tr'] > 0 and random.random() < state['dm_tr'] * dt * 20000:
                tr_y = CYL_Y + engine.x_tr * SCALE + 10
                particles.append(Particle(CRANK_X - engine.B/2*SCALE, tr_y + random.uniform(0, 15), (50, 200, 255), random.uniform(1, 4), random.uniform(-8, -3)))
                
            if state['dm_in'] > 0 and random.random() < state['dm_in'] * dt * 10000:
                particles.append(Particle(CRANK_X - 120, CRANK_Y + 20 + random.uniform(-10, 10), (0, 255, 100), random.uniform(3, 8), random.uniform(-1, 1)))
            
        # Spara punkter till PV-diagram (omvandla till cc och Bar)
        V_cyl_cc = (engine.V_c + engine.A_p * state['x']) * 1e6
        pv_cyl_points.append((V_cyl_cc, state['p_cyl'] / 100000.0)) 
        
        V_cr_cc = (engine.V_cr_min + engine.A_p * (2*engine.R - state['x'])) * 1e6
        pv_cr_points.append((V_cr_cc, state['p_cr'] / 100000.0))

    # Uppdatera partiklar
    particles = [p for p in particles if p.life > 0]
    for p in particles: p.update()

    # ================= RENDERING =================
    screen.fill(BG_COLOR)
    
    cyl_w = engine.B * SCALE
    cyl_h = 2 * engine.R * SCALE + 40
    cyl_rect = (CRANK_X - cyl_w/2, CYL_Y - 20, cyl_w, cyl_h)
    
    # Rita port-kanaler
    exh_y = CYL_Y + engine.x_exh * SCALE
    tr_y = CYL_Y + engine.x_tr * SCALE
    # Avgasrör
    pygame.draw.rect(screen, (80, 40, 40), (CRANK_X + cyl_w/2, exh_y, 60, engine.w_exh * SCALE))
    # Överströmningskanal
    pygame.draw.rect(screen, (40, 80, 100), (CRANK_X - cyl_w/2 - 40, tr_y, 40, engine.w_tr * SCALE + 40))
    
    # Rita Cylinder (genomskinlig)
    s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(s, CYL_COLOR, cyl_rect, border_radius=8)
    # Cylinder-väggar
    pygame.draw.rect(screen, (100, 100, 130), cyl_rect, width=4, border_radius=8)
    screen.blit(s, (0,0))
    
    # Vevhus
    pygame.draw.circle(screen, (50, 50, 65), (CRANK_X, CRANK_Y), engine.R * SCALE + 40, width=4)
    # Insugskanal med reedventil representation
    in_color = (60, 180, 80) if state['dm_in'] > 0 else (60, 80, 60)
    pygame.draw.rect(screen, in_color, (CRANK_X - engine.R*SCALE - 90, CRANK_Y + 5, 60, 30))
    
    # Tändstift
    pygame.draw.rect(screen, (200, 200, 200), (CRANK_X - 10, CYL_Y - 35, 20, 15))
    if engine.spark_active:
        pygame.draw.circle(screen, (255, 255, 150), (CRANK_X, CYL_Y - 15), 18)
    
    # Kolv
    piston_h = 45
    piston_y = CYL_Y + state['x'] * SCALE
    pygame.draw.rect(screen, PISTON_COLOR, (CRANK_X - cyl_w/2 + 2, piston_y, cyl_w - 4, piston_h), border_radius=3)
    
    # Vevaxel & Vevstake
    crank_x = CRANK_X + math.sin(engine.theta) * engine.R * SCALE
    crank_y = CRANK_Y - math.cos(engine.theta) * engine.R * SCALE
    
    # Vevstake (Linje mellan vevtapp och kolvtapp)
    piston_pin_y = piston_y + piston_h / 2
    pygame.draw.line(screen, (150, 150, 170), (crank_x, crank_y), (CRANK_X, piston_pin_y), 14)
    # Vevaxel-halva
    pygame.draw.line(screen, (180, 180, 200), (CRANK_X, CRANK_Y), (crank_x, crank_y), 20)
    
    # Tappar
    pygame.draw.circle(screen, (200, 50, 50), (int(crank_x), int(crank_y)), 8)
    pygame.draw.circle(screen, (50, 50, 50), (CRANK_X, int(piston_pin_y)), 6)
        
    # Rita Partiklar
    p_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for p in particles: p.draw(p_surf)
    screen.blit(p_surf, (0, 0))
        
    # Text Information
    texts = [
        f"Gaspådrag (Reed): {int(engine.throttle*100)}% [Upp/Ner]",
        f"RPM: {int(state['rpm'])}",
        f"Cyl Tryck: {state['p_cyl']/100000:.2f} Bar",
        f"Vevhus Tryck: {state['p_cr']/100000:.2f} Bar",
        f"Nettomoment: {state['torque']:.1f} Nm"
    ]
    for i, t in enumerate(texts):
        screen.blit(font.render(t, True, (220, 220, 230)), (20, 20 + i*25))
        
    # PV Diagram (Cylinder)
    diag_rect = (900, 30, 350, 280)
    pygame.draw.rect(screen, (30,30,40), diag_rect, border_radius=8)
    pygame.draw.rect(screen, (100,100,100), diag_rect, width=2, border_radius=8)
    screen.blit(small_font.render("PV-Diagram Cylinder (cc vs Bar)", True, (200,200,200)), (910, 40))
    
    if len(pv_cyl_points) > 2:
        mapped = []
        for v, p in pv_cyl_points:
            x = 900 + ((v - 10) / 140) * 350
            y = 310 - (min(p, 60) / 60) * 280
            mapped.append((x, y))
        pygame.draw.lines(screen, (255, 120, 120), False, mapped, 2)
        
    # PV Diagram (Vevhus)
    diag2_rect = (900, 350, 350, 280)
    pygame.draw.rect(screen, (30,40,30), diag2_rect, border_radius=8)
    pygame.draw.rect(screen, (100,100,100), diag2_rect, width=2, border_radius=8)
    screen.blit(small_font.render("PV-Diagram Vevhus (cc vs Bar)", True, (200,200,200)), (910, 360))
    
    if len(pv_cr_points) > 2:
        mapped2 = []
        for v, p in pv_cr_points:
            x = 900 + ((v - 150) / 100) * 350
            y = 630 - ((p - 0.5) / 1.0) * 280
            mapped2.append((x, y))
        pygame.draw.lines(screen, (120, 255, 120), False, mapped2, 2)

    pygame.display.flip()

pygame.quit()
sys.exit()
