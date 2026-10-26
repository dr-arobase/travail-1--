/*
 * Itération 1 - Porte magique (côté Arduino)
 *
 * La porte s'ouvre toute seule quand la caméra (Raspberry Pi / ordinateur)
 * reconnaît un visage autorisé.
 *
 * Composants (8 capteurs/actionneurs) :
 *   1. Bouton poussoir       -> active / désactive la porte
 *   2. Capteur PIR           -> détecte une présence et réveille la porte
 *   3. Capteur ultrason      -> déclenche la reconnaissance quand on s'approche,
 *                               et empêche la porte de se refermer sur quelqu'un
 *   4. Servomoteur           -> ouvre / ferme la porte (mouvement lent et fluide)
 *   5. LED RGB               -> effets lumineux (veille, analyse, arc-en-ciel, refus)
 *   6. Buzzer                -> mélodie magique, son de refus
 *   7. Afficheur LCD I2C     -> messages (« Bienvenue Marie », « Acces refuse »...)
 *   8. LED d'état            -> système ON / OFF
 *
 * Communication série (9600 bauds) avec le Raspberry Pi / l'ordinateur :
 *   Arduino -> PC : EVT:<evenement>, STATUS:<cle=valeur,...>, INFO:<texte>
 *   PC -> Arduino : OPEN:<nom>, OPEN, DENY, CLOSE, TOGGLE, STATUS
 *
 * Bibliothèques : Servo (incluse), LiquidCrystal I2C (Frank de Brabander)
 */

#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ---------- Broches ----------
const uint8_t PIN_BOUTON   = 2;
const uint8_t PIN_PIR      = 3;
const uint8_t PIN_TRIG     = 4;
const uint8_t PIN_ECHO     = 5;
const uint8_t PIN_BUZZER   = 8;
const uint8_t PIN_SERVO    = 9;
const uint8_t PIN_RGB_R    = 10;
const uint8_t PIN_RGB_V    = 11;
const uint8_t PIN_RGB_B    = 12;
const uint8_t PIN_LED_ETAT = 13;
// LCD I2C : SDA -> A4, SCL -> A5

// ---------- Paramètres ----------
const bool RGB_ANODE_COMMUNE      = false;  // true si la patte commune de la LED RGB va au 5V
const int  DIST_RECONNAISSANCE_CM = 40;     // on lance la reconnaissance sous cette distance
const int  DIST_SECURITE_CM       = 15;     // la porte ne se ferme pas si quelqu'un est si proche
const int  ANGLE_FERME            = 0;
const int  ANGLE_OUVERT           = 90;
const unsigned long PAS_SERVO_MS        = 15;    // vitesse d'ouverture (ms par degré)
const unsigned long DELAI_REPONSE_PC    = 8000;  // temps max pour reconnaître le visage
const unsigned long DUREE_OUVERTURE     = 5000;
const unsigned long DUREE_REFUS         = 3000;
const unsigned long DELAI_RETOUR_VEILLE = 10000; // sans présence pendant 10 s -> veille
const unsigned long PERIODE_CAPTEURS    = 100;
const unsigned long PERIODE_STATUS      = 1000;
const unsigned long ANTI_REBOND         = 50;

// ---------- Mélodies (fréquences en Hz) ----------
const int MELODIE_MAGIQUE[] = {523, 659, 784, 1047, 1319, 1568, 2093};  // arpège do majeur
const int MELODIE_REFUS[]   = {330, 220};
const int MELODIE_ON[]      = {784, 1047};
const int MELODIE_OFF[]     = {1047, 784};

// ---------- Objets ----------
LiquidCrystal_I2C lcd(0x27, 16, 2);  // essayer 0x3F si l'écran reste vide
Servo porte;

// ---------- État ----------
enum Etat { VEILLE, PRESENCE, RECONNAISSANCE, OUVERTE, REFUSEE };
const char* NOMS_ETAT[] = {"VEILLE", "PRESENCE", "RECONNAISSANCE", "OUVERTE", "REFUSEE"};
Etat etat = VEILLE;

bool systemeActif = false;
bool presence     = false;
bool reconnaissanceArmee = true;  // il faut reculer avant une nouvelle tentative
int  distanceCm   = 999;
String nomVisiteur = "";
unsigned long tEtat = 0;
unsigned long tDernierePresence = 0;

int angleActuel = ANGLE_FERME;
int angleCible  = ANGLE_FERME;
unsigned long tServo = 0;

const int* melodie = nullptr;
uint8_t longueurMelodie = 0;
uint8_t indexNote = 0;
unsigned long dureeNote = 0;
unsigned long tNote = 0;

bool etatBoutonStable  = HIGH;
bool dernierEtatBouton = HIGH;
unsigned long tRebond  = 0;

unsigned long tCapteurs = 0;
unsigned long tStatus   = 0;
bool lcdAMettreAJour    = true;

String tampon = "";

// ======================================================================
void setup() {
  Serial.begin(9600);

  pinMode(PIN_BOUTON, INPUT_PULLUP);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_RGB_R, OUTPUT);
  pinMode(PIN_RGB_V, OUTPUT);
  pinMode(PIN_RGB_B, OUTPUT);
  pinMode(PIN_LED_ETAT, OUTPUT);

  porte.attach(PIN_SERVO);
  porte.write(ANGLE_FERME);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Porte magique");
  lcd.setCursor(0, 1);
  lcd.print("Demarrage...");
  delay(1000);
  setCouleur(false, false, false);

  Serial.println(F("INFO:Arduino pret"));
  envoyerStatus();
}

void loop() {
  unsigned long maintenant = millis();

  lireBouton();
  lireSerie();

  if (maintenant - tCapteurs >= PERIODE_CAPTEURS) {
    tCapteurs = maintenant;
    distanceCm = lireDistanceCm();
    presence = digitalRead(PIN_PIR) == HIGH || distanceCm <= DIST_RECONNAISSANCE_CM;
    if (presence) tDernierePresence = maintenant;
  }

  if (systemeActif) gererEtats();
  gererServo();
  gererMelodie();
  gererLeds();

  if (maintenant - tStatus >= PERIODE_STATUS) {
    tStatus = maintenant;
    envoyerStatus();
  }
  if (lcdAMettreAJour) majAffichage();
}

// ---------- Machine à états de la porte ----------
void gererEtats() {
  unsigned long ecoule = millis() - tEtat;

  switch (etat) {
    case VEILLE:
      if (presence) {
        reconnaissanceArmee = true;
        changerEtat(PRESENCE);
        Serial.println(F("EVT:PRESENCE_DETECTEE"));
      }
      break;

    case PRESENCE:
      if (!reconnaissanceArmee && distanceCm > DIST_RECONNAISSANCE_CM + 10) {
        reconnaissanceArmee = true;
      }
      if (reconnaissanceArmee && distanceCm <= DIST_RECONNAISSANCE_CM) {
        reconnaissanceArmee = false;
        changerEtat(RECONNAISSANCE);
        Serial.println(F("EVT:VISAGE_DEMANDE"));  // le PC lance la reconnaissance
      } else if (millis() - tDernierePresence > DELAI_RETOUR_VEILLE) {
        changerEtat(VEILLE);
        Serial.println(F("EVT:VEILLE"));
      }
      break;

    case RECONNAISSANCE:
      if (ecoule > DELAI_REPONSE_PC) {
        Serial.println(F("INFO:Pas de reponse du PC"));
        refuserAcces();  // par sécurité, la porte reste fermée
      }
      break;

    case OUVERTE:
      if (ecoule > DUREE_OUVERTURE && distanceCm > DIST_SECURITE_CM) {
        fermerPorte();
      }
      break;

    case REFUSEE:
      if (ecoule > DUREE_REFUS) changerEtat(PRESENCE);
      break;
  }
}

void changerEtat(Etat nouveau) {
  etat = nouveau;
  tEtat = millis();
  lcdAMettreAJour = true;
}

void ouvrirPorte(const String& nom) {
  nomVisiteur = nom;
  angleCible = ANGLE_OUVERT;
  changerEtat(OUVERTE);
  jouerMelodie(MELODIE_MAGIQUE, 7, 120);
  Serial.print(F("EVT:PORTE_OUVERTE:"));
  Serial.println(nom);
}

void fermerPorte() {
  angleCible = ANGLE_FERME;
  reconnaissanceArmee = false;
  changerEtat(PRESENCE);
  Serial.println(F("EVT:PORTE_FERMEE"));
}

void refuserAcces() {
  changerEtat(REFUSEE);
  jouerMelodie(MELODIE_REFUS, 2, 300);
  Serial.println(F("EVT:ACCES_REFUSE"));
}

// ---------- Bouton poussoir (avec anti-rebond) ----------
void lireBouton() {
  bool lecture = digitalRead(PIN_BOUTON);
  if (lecture != dernierEtatBouton) {
    tRebond = millis();
  }
  if (millis() - tRebond > ANTI_REBOND && lecture != etatBoutonStable) {
    etatBoutonStable = lecture;
    if (etatBoutonStable == LOW) {
      basculerSysteme();
    }
  }
  dernierEtatBouton = lecture;
}

void basculerSysteme() {
  systemeActif = !systemeActif;
  angleCible = ANGLE_FERME;
  changerEtat(VEILLE);
  if (systemeActif) {
    jouerMelodie(MELODIE_ON, 2, 120);
    Serial.println(F("EVT:SYSTEME_ON"));
  } else {
    jouerMelodie(MELODIE_OFF, 2, 120);
    Serial.println(F("EVT:SYSTEME_OFF"));
  }
}

// ---------- Capteur ultrason ----------
int lireDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long duree = pulseIn(PIN_ECHO, HIGH, 25000UL);  // ~4 m max
  if (duree == 0) return 999;                             // rien détecté
  return duree / 58;
}

// ---------- Servomoteur : ouverture lente, degré par degré ----------
void gererServo() {
  if (angleActuel == angleCible || millis() - tServo < PAS_SERVO_MS) return;
  tServo = millis();
  angleActuel += (angleCible > angleActuel) ? 1 : -1;
  porte.write(angleActuel);
}

// ---------- Buzzer : mélodie non bloquante ----------
void jouerMelodie(const int* notes, uint8_t longueur, unsigned long duree) {
  melodie = notes;
  longueurMelodie = longueur;
  indexNote = 0;
  dureeNote = duree;
  tNote = millis() - duree;  // la première note part tout de suite
}

void gererMelodie() {
  if (melodie == nullptr || millis() - tNote < dureeNote) return;
  if (indexNote >= longueurMelodie) {
    melodie = nullptr;
    noTone(PIN_BUZZER);
    return;
  }
  tone(PIN_BUZZER, melodie[indexNote], dureeNote * 9 / 10);
  indexNote++;
  tNote = millis();
}

// ---------- LED RGB et LED d'état ----------
void setCouleur(bool r, bool v, bool b) {
  digitalWrite(PIN_RGB_R, r != RGB_ANODE_COMMUNE);
  digitalWrite(PIN_RGB_V, v != RGB_ANODE_COMMUNE);
  digitalWrite(PIN_RGB_B, b != RGB_ANODE_COMMUNE);
}

void gererLeds() {
  unsigned long t = millis();
  digitalWrite(PIN_LED_ETAT, systemeActif);

  if (!systemeActif) {
    setCouleur(false, false, false);
    return;
  }
  switch (etat) {
    case VEILLE: {         // petit éclat violet toutes les 2 s
      bool eclat = t % 2000 < 100;
      setCouleur(eclat, false, eclat);
      break;
    }
    case PRESENCE:
      setCouleur(false, false, true);              // bleu
      break;
    case RECONNAISSANCE: {                         // bleu / cyan qui alterne
      bool phase = (t / 250) % 2;
      setCouleur(false, phase, true);
      break;
    }
    case OUVERTE: {        // arc-en-ciel
      static const uint8_t ARC[6][3] = {
        {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 1, 1}, {0, 0, 1}, {1, 0, 1}};
      const uint8_t* c = ARC[(t / 150) % 6];
      setCouleur(c[0], c[1], c[2]);
      break;
    }
    case REFUSEE: {        // rouge clignotant
      bool allume = (t / 200) % 2;
      setCouleur(allume, false, false);
      break;
    }
  }
}

// ---------- Afficheur LCD ----------
void afficher(const String& ligne1, const String& ligne2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(ligne1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(ligne2.substring(0, 16));
}

void majAffichage() {
  lcdAMettreAJour = false;
  if (!systemeActif) {
    afficher("Porte magique", "Systeme OFF");
    return;
  }
  switch (etat) {
    case VEILLE:         afficher("Porte magique", "Zzz...");            break;
    case PRESENCE:       afficher("Bonjour !", "Approchez-vous");        break;
    case RECONNAISSANCE: afficher("Regardez la", "camera...");           break;
    case OUVERTE:        afficher("Bienvenue", nomVisiteur);             break;
    case REFUSEE:        afficher("Acces refuse", "Visage inconnu");     break;
  }
}

// ---------- Communication série ----------
void lireSerie() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      tampon.trim();
      traiterCommande(tampon);
      tampon = "";
    } else if (tampon.length() < 32) {
      tampon += c;
    }
  }
}

void traiterCommande(const String& cmd) {
  if (cmd == "OPEN" || cmd.startsWith("OPEN:")) {
    if (systemeActif) {
      ouvrirPorte(cmd.length() > 5 ? cmd.substring(5) : String("Ami"));
    }
  } else if (cmd == "DENY") {
    if (etat == RECONNAISSANCE) refuserAcces();
  } else if (cmd == "CLOSE") {
    if (etat == OUVERTE) fermerPorte();
  } else if (cmd == "TOGGLE") {
    basculerSysteme();
  } else if (cmd == "STATUS") {
    envoyerStatus();
  } else if (cmd.length() > 0) {
    Serial.print(F("INFO:Commande inconnue "));
    Serial.println(cmd);
  }
}

void envoyerStatus() {
  Serial.print(F("STATUS:actif="));
  Serial.print(systemeActif);
  Serial.print(F(",etat="));
  Serial.print(NOMS_ETAT[etat]);
  Serial.print(F(",presence="));
  Serial.print(presence);
  Serial.print(F(",distance="));
  Serial.print(distanceCm);
  Serial.print(F(",angle="));
  Serial.println(angleActuel);
}
