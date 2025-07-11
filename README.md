Aplicatia acopera toate cerintele discutate si am mai adaugat si eu anumite lucruri pe care le-am considerat ca ajuta sau ca sunt necesare:

Am folosit:
  Flask cu arhitectura Blueprint pentru organizarea modulară a aplicației
  PostgreSQL pentru baza de date
  SQLAlchemy implementează maparea ORM declarativă pentru gestionarea bazei de date
  APScheduler gestionează programarea job-urilor
  Selenium WebDriver pentru scraping pe Facebook ca metoda principala si scraping folosind html ca metoda secundara in cazul in care esueaza prima metoda
  Chart.js pentru vizualizarea interactivă a datelor cu grafice dinamice
  BeautifulSoup4 gestionează parsarea HTML-ului și extragerea conținutului
  Requests pentru gestionarea sesiunilor HTTP și logica de retry
  Pytz pentru gestionarea timezone-urilor și conversiilor temporale pentru România

Pentru testare am folosit un interval de scraping la 2 minute pentru ca nu puteam sa astept cate 2 ore. Pentru scraping la 2 ore trebuie setat parametrul SCRAPER_TESTING_MODE=false din fisierul run.py.

Fluxul de date și procesarea:

  La executarea fisierului run.py pornesc toate scraperele si ruleaza in paralel. Cel pentru facebook realizeaza tot procesul necesar pana cand logarea se efectueaza cu succes dar asteapta ca utilizatorul sa faca interogarea profilului dorit. Celelalte doua scrapere se executa conform scheduler-ului pana cand aplicatia este inchisa.
  Pentru adevarul.ro am folosit ca metoda principala extragerea datelor din RSS feed deoarece am observat ca il tin actualizat in timp real si se gasesc intotdeauna ultimele 50 de stiri, si ca metoda secundata, dar nu optionala, se face scraping html si se extrag stirile care nu sunt detectate ca duplicate.
  Pentru biziday.ro am folosit ca metoda principala scraping html deoarece RSS feed-ul nu il tin actualizat. Publica cateva stiri pe zi care se pot extrage cu lejeritate de pe pagina de home. Ca metoda secundara se preiau date si din RSS feed.
  Pentru Facebook folosesc ca metoda principala scraping prin Selenium WebDriver deoarece majoritatea profilurilor nu sunt publice si se pot extrage foarte putine informatii folosind doar scraping html fara logare. Ca metoda secundara in cazul in care logarea esueaza sau din orice alte motive nu se pot extrage date prin Selenium WebDriver, se foloseste si scraping html.

  Pentru sursele de stiri sunt salvate titlul, descrierea, continutul intregului articol, data si ora publicarii, data si ora actualizarii articolului, data si ora salvarii in baza de date, hash-ul continutului.
  Hash-ul se calculeaza folosind o funcție PostgreSQL `generate_content_hash()` care se execută automat ca trigger la fiecare operație INSERT sau UPDATE pe tabela `news_articles`. Această funcție calculează un hash SHA-256 unic prin combinarea deterministă a trei câmpuri esențiale: titlul articolului, rezumatul și link-ul complet. Hash-ul se generează prin concatenarea ordonată a câmpurilor (title + summary + link), urmată de aplicarea algoritmului SHA-256 și encodarea rezultatului în format hexadecimal pentru obținerea unui string de 64 de caractere. Acest proces garantează că două articole cu același conținut esențial vor avea același hash, indiferent de diferențele minore de formatare.
  Strategia Multi-Nivel de Detectare

  Am implementat o arhitectură cu trei niveluri independente de detectare pentru asigurarea completă a unicității:

  Nivel 1 - Verificarea Unității Link-ului: - verifică unicitatea absolută a URL-ului articolului prin constraint-ul UNIQUE pe coloana `link`. URL-urile se normalizează automat prin eliminarea parametrilor GET (?param=value), fragmentelor de ancoră (#section) și trailing slash-urilor pentru comparație precisă. Aceasta previne salvarea aceluiași articol de pe același URL de multiple ori.
  Nivel 2 - Verificarea Content Hash: - Dacă un articol trece primul nivel (URL diferit), sistemul verifică imediat content_hash-ul pentru a detecta republicările aceluiași conținut pe URL-uri diferite. Acest mecanism este esențial pentru identificarea articolelor duplicate care sunt republicate pe subdomenii diferite sau cu parametri de tracking diferiți.
  Nivel 3 - Verificarea la Nivel de Aplicație: - Nivelul final implementează verificări suplimentare în codul Python pentru detectarea similarităților semantice prin:
    - Normalizarea titlurilor cu eliminarea diacriticelor și comparația case-insensitive
    - Calcularea similarității textuale folosind algoritmi de diferența Levenshtein
    - Identificarea pattern-urilor comune de republicare și reformulare

  Mecanismul de actualizare - M-am gandit ca ar fi folositor ca atunci cand un articol este gasit ca duplicat sa nu fie ignorat complet, ci sa se verifice daca data si ora actualizarii s-au schimbat. Daca s-au schimbat inseamna ca articolul a suferit modificari intre timp si trebuie extras din nou.

Implementarea frontend:
  /news - tabelul cu toate articolele stocate care permite cautare dupa cuvinte cheie, filtrare dupa sursa si sortare dupa titlu, descriere, data publicarii. Am pus si un buton care redirectioneaza catre articolul respectiv si de asemenea este afisat numarul total de articole, si numarul de articole pe susrsa.
  /stats - graficele si statisticile cerute. Se poate face filtrare atat dupa data publicarii cat si in functie de de intervalul orar, dar si in functie de sursa. Statisticile privind media lungimii continutului se calculeaza pe baza numarului de cuvinte ale intregului articol.
  /facebook - permite interogarea profilului de facebook dat de utilizator. Se poate introduce username-ul, id-ul, sau link-ul profilului. Sunt afisate datele extrase.
  /facebook-profiles - api-ul pentru datele Facebook salvate
  /sources - api-ul pentru toate articolele salvate
