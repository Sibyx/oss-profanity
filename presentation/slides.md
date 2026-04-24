---
theme: seriph
layout: cover
background: '#fff'
title: "Application Aspects in Database Systems"
info: |
  DBS Course — FIIT STU 2026
  Application Aspects in Database Systems

  ORM patterns, schema migrations, the deployment ladder from laptop to SaaS,
  database operations, and security.
author: Jakub Dubec
transition: slide-left
mdc: true
lineNumbers: true
colorSchema: light
fonts:
  sans: Open Sans
  mono: Fira Code
drawings:
  persist: false
---

# Application Aspects in Database Systems

<div class="mt-2 text-lg opacity-80">
  Database Systems — FIIT STU
</div>

<div class="abs-bl m-8">
  <img src="/images/logo_fiit.svg" class="h-10" alt="FIIT STU" />
</div>

<div class="abs-br m-8 text-sm opacity-40">
  Jakub Dubec · 2026
</div>

<!--
Welcome to the Application Aspects lecture. This year we assume this is your
FIRST lecture meeting Object-Relational Mapping (ORM) — so we will build the
vocabulary from scratch. But we will not stop there: we will also climb the
deployment ladder from `psql` on your laptop all the way to managed SaaS
PostgreSQL, name the patterns that keep production databases alive, and end
with live SQL injection in the browser. By the end you should have both the
conceptual vocabulary AND the operational intuition to build a database-backed
application that survives contact with real users.
-->

---
layout: center
---

# "I want to save a `User` to the database." 💾

<v-click>

What does the system actually do between `user.save()` and the row hitting disk?

</v-click>

<v-click>

And once it *does* hit disk — **who keeps that disk alive at 3 a.m.?**

</v-click>

<!--
Our guiding question for the whole lecture. A single line of code triggers a
surprising amount of machinery: mapping, tracking, transactions, connection
handling, escaping, failover, backups. We'll pull the covers back on all of it.
The second beat ("who keeps it alive at 3 a.m.") is the *application aspects*
framing — this is not a database-internals lecture, it's a lecture about living
with a database in production.
-->

---

# Today's Agenda

<v-clicks>

1. **What is an ORM?** — from SQL to objects in four layers
2. **ORM Design Patterns** — Active Record, Data Mapper, and friends
3. **Schema Migrations** — version control for your database
4. **The Deployment Ladder** — laptop → Docker → Kubernetes → SaaS
5. **Operations** — pooling, observability, backups
6. **Security** — injection (live!), secrets, TLS, row-level security
7. **Practical Examples** — Django · SQLAlchemy · Hibernate
8. **Quizzes & Further Reading**

</v-clicks>

<!--
Nine beats in ~90 minutes. We build the story in layers: what an ORM is, what
it's made of, how the schema evolves, where it runs, how it stays alive, how
it stays safe. Practical code examples tie the abstract back to real frameworks
at the end. Each section loops back to the guiding question from a new angle.
-->

---
layout: section
---

# What is an ORM?

*Four layers between you and the database*

---

# The Object / Relational Impedance Mismatch

<div class="grid grid-cols-2 gap-6 mt-6">
<div>

**An object has…**

- Identity (a reference)
- State (fields)
- Behaviour (methods)
- References to other objects
- Inheritance, polymorphism

```python
class User:
    id: int
    name: str
    friends: list["User"]
    def greet(self): ...
```

</div>
<div>

**A row has…**

- A primary key
- Typed columns
- No behaviour
- Foreign keys (not references)
- No inheritance

```sql
CREATE TABLE users (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE friendships (
  user_id   INTEGER REFERENCES users,
  friend_id INTEGER REFERENCES users
);
```

</div>
</div>

<v-click>

> The two halves don't line up. **Something** has to translate between them. That something is the ORM.

</v-click>

<!--
Coin the phrase "object/relational impedance mismatch" here — students will
hear it the rest of their careers. Ted Neward's 2006 essay "The Vietnam of
Computer Science" is the classic rant on it; not on slide, just in notes.
The asymmetry matters: objects are graphs, rows are tuples. ORMs bridge.
-->

---

# Four Ways to Talk to a Database

Four distinct **layers** of abstraction — each adds ergonomics and hides more SQL than the one below it.

<div class="grid grid-cols-2 gap-4 mt-4 text-sm">

<div class="p-3 border-l-4 border-gray-400 bg-gray-50 rounded">
<div class="font-semibold">1 · Raw driver</div>
<div class="opacity-70 text-xs mt-1">psycopg · pg · JDBC</div>
<div class="mt-2">You write SQL strings, you manage the cursor, you live with it.</div>
</div>

<div class="p-3 border-l-4 border-blue-400 bg-blue-50 rounded">
<div class="font-semibold">2 · Query builder</div>
<div class="opacity-70 text-xs mt-1">Knex · jOOQ · SQLAlchemy Core</div>
<div class="mt-2">Programmatic SQL — <code>.select().from().where()</code>. Still no objects.</div>
</div>

<div class="p-3 border-l-4 border-indigo-400 bg-indigo-50 rounded">
<div class="font-semibold">3 · Micro-ORM</div>
<div class="opacity-70 text-xs mt-1">Dapper · asyncpg helpers</div>
<div class="mt-2">Row → object mapping, minimal magic. You still write SQL.</div>
</div>

<div class="p-3 border-l-4 border-sky-500 bg-sky-50 rounded">
<div class="font-semibold">4 · Full ORM</div>
<div class="opacity-70 text-xs mt-1">Django · Hibernate · SQLAlchemy</div>
<div class="mt-2">Objects, relationships, lazy loading, migrations, the lot.</div>
</div>

</div>

<v-click>

> Climbing up: **less SQL in your code**, more abstraction, more learning curve. Each layer trades control for ergonomics.

</v-click>

<!--
Most of the industry lives at layers 1 or 4, with growing interest in 2 and 3.
The point is not "ORMs are better than drivers" — it's that these are distinct
tools for distinct jobs. A scripting pipeline often wants a raw driver. A
typical web app usually wants a full ORM. Neither is wrong; pick the layer.
-->

---

# What a Full ORM Gives You

<v-clicks>

- **Mapping** — tables ↔ classes, rows ↔ instances, columns ↔ fields
- **Query DSL** — write filters in your language, not in SQL strings
- **Relationships** — `post.author` returns the `User` object, not an ID
- **Parameterisation by default** — SQL injection protection for free
- **Schema migrations** — versioned `ALTER TABLE` as part of your code
- **Transactions & identity** — the same row → the same object in a session
- **Lazy & eager loading** — tune what's fetched without rewriting queries

</v-clicks>

<v-click>

> An ORM is not magic. It is **a stack of well-named patterns** layered on top of the driver. We will name every one of those patterns next.

</v-click>

<!--
This is the "why bother" slide. Each bullet is something you'd have to write
by hand if you used the raw driver. None of them are rocket science — but all
of them are error-prone and boring. ORMs automate the boring bits so you have
budget left for the interesting bits (schema design, query planning, ops).
-->

---

# What a Full ORM Does NOT Give You

<v-clicks>

- 🧠 **Schema design** — normalisation, keys, constraints — still on you
- 📈 **Query-plan intuition** — the ORM emits SQL; the *plan* is PostgreSQL's problem
- 🔍 **Performance** — N+1 queries will still hurt until you see them
- ⚖️ **Correctness under load** — isolation levels, locking, deadlocks
- 🔐 **Access control** — which user can touch which rows
- 🧹 **Operational hygiene** — pooling, backups, monitoring — all still on you

</v-clicks>

<v-click>

> The ORM is a **layer**, not a wall. When the app gets slow or wrong, you will have to look *through* it. Plan for that.

</v-click>

<!--
Equally important. Students sometimes leave their first ORM lecture thinking
"I never have to write SQL again" — which is only true until production. The
ORM hides complexity; it does not remove it. This slide sets up the whole
rest of the lecture: everything we cover after patterns is stuff the ORM
*doesn't* do for you.
-->

---

<div class="pg-trivia">
  <div class="pg-trivia-title">🐘 Postgres trivia · MVCC</div>
  <div class="pg-trivia-body">
    An <code>UPDATE</code> in PostgreSQL never overwrites a row in place. It writes a
    <em>new</em> tuple and marks the old one dead. <code>VACUUM</code> is what eventually reclaims
    the dead ones. This is <strong>Multi-Version Concurrency Control (MVCC)</strong> — the reason
    readers don't block writers and writers don't block readers. It's a design choice from the original
    POSTGRES paper (Stonebraker &amp; Rowe, 1986) that 40 years later is still a competitive advantage.
  </div>
</div>

<v-click>

<div class="cool-tip">
  <div class="cool-tip-title">💡 Cool tip · use <code>RETURNING</code></div>
  PostgreSQL lets <code>INSERT</code> / <code>UPDATE</code> / <code>DELETE</code> return rows in one round-trip:
  <code>INSERT INTO users (name) VALUES ('Alice') RETURNING id, created_at;</code> — no follow-up <code>SELECT</code> needed.
</div>

</v-click>

<!--
Keep the first trivia lightweight. The cool-tip pattern introduces the
yellow callout we'll reuse. RETURNING is a quiet superpower — it saves one
round-trip per write, which matters at 3000 QPS. Most ORMs expose it via
.returning() or similar; learn your ORM's idiom.
-->

---
layout: section
---

# ORM Design Patterns

*The patterns your ORM is made of*

---

# Active Record Pattern

> A database table is wrapped by a class; each **instance is a row**.

<v-clicks>

- Properties map to columns
- Methods like `save()`, `update()`, `delete()` encapsulate SQL
- **Examples**: Rails ActiveRecord, Laravel Eloquent, Django ORM
- ✅ Simple, fast to build CRUD, easy to teach
- ☠️ Leads to "fat models"; the domain object is tightly bound to the schema

</v-clicks>

<!--
Named by Martin Fowler in *Patterns of Enterprise Application Architecture*
(2003). Each object = one row, plus CRUD methods. The appeal is no SQL to
write. The trap is that once business logic grows, the model class becomes
a god object that knows about HTTP, email, billing, AND the database.
-->

---

# Active Record Example (Django)

```python
from django.db import models

class Post(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    published_at = models.DateTimeField(auto_now_add=True)

# Using the model
post = Post(title="Hello", content="First post")
post.save()                                     # INSERT INTO app_post ...
post.title = "Hello!"
post.save()                                     # UPDATE app_post SET ... WHERE id = ...

Post.objects.filter(title__icontains="hello")   # SELECT ... WHERE title ILIKE '%hello%'
```

<v-click>

The `Post` class **is** the query interface **and** the row. That's the pattern in one sentence.

</v-click>

<!--
Point at every line and name the SQL it becomes. The "icontains" lookup is a
good place to mention that Django writes the LIKE pattern for you AND
parameterises the value — no manual escaping, no injection risk. The INSERT
vs UPDATE dispatch happens based on whether the instance has a primary key.
-->

---

# Data Mapper Pattern

> A separate **mapper** layer transfers data between objects and the database.

<v-clicks>

- Domain objects contain behaviour but **no persistence code**
- A mapper / repository / session does the SQL
- **Examples**: Hibernate (Java), SQLAlchemy (Python), Doctrine (PHP)
- ✅ Clean separation of concerns, easy to test in isolation, handles complex mappings
- ☠️ More moving parts, more configuration, harder to debug first time

</v-clicks>

<v-click>

> Active Record says *"the object knows how to save itself."* Data Mapper says *"somebody else knows how to save this object."* That one sentence is the entire difference.

</v-click>

<!--
The core philosophical difference. Data Mapper is what you want when your
domain has real behaviour — invariants, workflows, state machines — that
shouldn't know or care about rows. Active Record is what you want when CRUD
is 90% of your use case.
-->

---

# Data Mapper Example (SQLAlchemy)

````md magic-move
```python
# 1) Declare the mapping — no persistence methods on the class
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    id    = Column(Integer, primary_key=True)
    name  = Column(String)
    price = Column(Integer)
```

```python
# 2) Work through a Session — the mapper
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine  = create_engine("postgresql://user:pass@localhost:5432/mydb")
Session = sessionmaker(bind=engine)
session = Session()

prod = Product(name="Widget", price=100)
session.add(prod)        # "track this as new"
session.commit()         # now the INSERT actually happens

widgets = session.query(Product).filter_by(name="Widget").all()
```
````

<!--
Notice Product has no save() or delete() method — the mapping class is data
plus metadata, nothing else. The Session plays three roles at once: Data Mapper
(it translates), Identity Map (it dedupes), and Unit of Work (it batches). We'll
name each of those explicitly in a moment.
-->

---

# Repository Pattern

> A **collection-like** interface for domain objects. Hides the mapper behind one cohesive API per aggregate.

<v-clicks>

- Looks like an in-memory `Set<User>` to the caller — `.add()`, `.remove()`, `.findById()`, `.findByEmail()`
- Internally delegates to a Data Mapper / Session / ORM query
- **Examples**: Spring Data `CrudRepository`, .NET EF `DbSet`, MikroORM `EntityRepository`
- ✅ Domain code never imports `Session` / `EntityManager` directly — testable, mockable
- ☠️ Easy to pile up custom finder methods until it's a god object again

</v-clicks>

<v-click>

> Data Mapper says *"somebody else saves this."* Repository says *"somebody else also **finds** it for me, and looks like a plain collection while doing so."*

</v-click>

<!--
Repository was named by Evans in Domain-Driven Design (2003) and refined by
Fowler in PEAA. The key move beyond Data Mapper is that the Repository is
*per-aggregate*, not per-table, and its interface is collection-shaped rather
than CRUD-shaped. In practice, a well-designed Repository reads like domain
language: `orders.placedBy(customer)`, not `orderMapper.findByCustomerId(id)`.
-->

---

# Repository Example (Python)

```python
class UserRepository:
    def __init__(self, session):
        self._session = session

    # Collection-shaped API — hides SQLAlchemy behind domain verbs
    def add(self, user: User) -> None:
        self._session.add(user)

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def find_by_email(self, email: str) -> User | None:
        return self._session.query(User).filter_by(email=email).one_or_none()

    def active_since(self, cutoff: date) -> list[User]:
        return (self._session.query(User)
                             .filter(User.last_seen >= cutoff)
                             .all())
```

<v-click>

Business logic now depends on `UserRepository` — **not** on `Session`, not on SQL, not on SQLAlchemy at all.

</v-click>

<!--
This is the level at which Domain-Driven Design operates. The Repository is
where the infrastructure-layer abstraction stops leaking into the domain
layer. Swap SQLAlchemy for Mongo? You reimplement UserRepository; domain
code is untouched. Mock UserRepository in tests? One-line subclass with an
in-memory list.
-->

---

# Active Record vs. Data Mapper vs. Repository

| Aspect       | **Active Record**                   | **Data Mapper**                            | **Repository**                                |
|--------------|-------------------------------------|--------------------------------------------|-----------------------------------------------|
| Shape        | Row = object with CRUD methods      | Session + bare domain object               | Collection-like facade over the mapper        |
| Coupling     | Strong — object ↔ table             | Weak — domain object doesn't know about DB | Weakest — domain doesn't know about mapper    |
| Complexity   | Low                                 | Medium                                     | Medium + one interface per aggregate          |
| Best fit     | CRUD apps, admin panels, prototypes | Complex domains, DDD                       | DDD, hexagonal architecture, testable domains |
| Typical ORMs | Django, Rails AR, Eloquent          | Hibernate, SQLAlchemy, Doctrine            | Spring Data, EF Core, MikroORM                |

<v-click>

> Django *feels* like Active Record, but `QuerySet` quietly behaves like a Data Mapper layer. Real ORMs are almost always **hybrids** — labels help, but don't believe them too hard.

</v-click>

<!--
The hybrid point matters. Students sometimes try to classify every ORM into
one bucket. Most modern ORMs cherry-pick features from both camps. What
matters is recognising which pattern is in play *in a given operation*, not
what label the library wears on the tin.
-->

---

# Table Data Gateway

> One class per table. All SQL for that table lives inside it.

<v-clicks>

- Methods like `find_all()`, `find_by_id()`, `insert()`, `update()`, `delete()`
- Still close to SQL — no automatic mapping to rich domain objects
- Common in "DAO layer" code, especially pre-ORM Java/PHP
- ✅ Keeps SQL out of the domain; clear single responsibility
- ☠️ Lots of nearly-identical code, one boilerplate class per table

</v-clicks>

```python
class UsersGateway:
    def find_by_email(self, email):
        self.cur.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        return self.cur.fetchone()

    def insert_user(self, name, email):
        self.cur.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id",
            (name, email),
        )
        return self.cur.fetchone()[0]
```

<!--
Historically a stepping stone towards ORMs. If you're not ready for a full
ORM, this is a perfectly respectable layer — and it's roughly what ORMs
generate internally. Note the `%s` placeholders: gateways protect you from
injection too, simply because writing parameterised queries is the idiom.
-->

---

# Row Data Gateway

> One class per **row** — "Active Record Lite".

<v-clicks>

- Fields map to columns; methods like `update()`, `delete()` act on *this one row*
- No domain logic — just row-shaped data with SQL attached
- Often lives inside a Table Data Gateway implementation
- ✅ Convenient when you want row-level helpers without a full ORM
- ☠️ Without an Identity Map, you can end up with **two objects for the same row**

</v-clicks>

<v-click>

> Modern ORMs have mostly eaten this pattern. You'll see it in *legacy* code or the guts of a hand-rolled persistence layer.

</v-click>

<!--
The distinction from Active Record is subtle and mostly historical. Worth
naming so students recognise it in Fowler's PEAA, but in 2026 you'll rarely
implement it deliberately. The "two objects for one row" failure mode
motivates the Identity Map pattern a few slides later.
-->

---

# Lazy Loading

> Don't fetch it until somebody touches it.

<v-clicks>

- Related objects return as **proxies** that trigger a query on first access
- Saves memory and bandwidth when the related data isn't used
- ☠️ Creates the **N+1 query problem** in loops
- Opt into **eager loading** (`select_related`, `prefetch_related`, `JOIN FETCH`) when you know you'll need the data

</v-clicks>

<!--
Lazy loading is the single biggest cause of "it was fast on my laptop, dies in
production" performance stories. Teach the ORM toggle for the language you're
teaching; the vocabulary differs per framework but the mechanism is identical.
-->

---

# Lazy Loading — Sequence

<div class="diagram-fit">

```mermaid {scale: 0.7}
sequenceDiagram
    participant App as Application
    participant ORM as ORM / Session
    participant DB as Database

    App->>ORM: load Post #42
    ORM->>DB: SELECT * FROM posts WHERE id = 42
    DB-->>ORM: row
    ORM-->>App: Post object (comments = <proxy>)

    Note over ORM: comments not loaded yet

    App->>ORM: read post.comments
    ORM->>DB: SELECT * FROM comments WHERE post_id = 42
    DB-->>ORM: rows
    ORM-->>App: real [Comment, Comment, ...]
```

</div>

<!--
Walk through the numbers. Loading 100 posts and reading .comments on each in
a loop is 1 + 100 queries. With prefetch_related / JOIN FETCH it becomes 2.
Two orders of magnitude of latency hidden behind an attribute access.
-->

---

# Identity Map

> Each row has **exactly one** in-memory object within a session.

<v-clicks>

- Fetching `User(id=42)` twice returns the **same Python/Java object**, not two copies
- Second lookup is a cache hit — **no SQL**
- Prevents the "two objects, one row, divergent state" bug
- Scoped to a **session / unit of work** — typically one request in a web app

</v-clicks>

<v-click>

> This is why SQLAlchemy or Hibernate sometimes "skip" a query you expected — it's not broken, it's the identity map doing its job.

</v-click>

<!--
The quiet pattern that prevents a whole class of bugs. Without it, two parts
of your code can each edit "the same" user and only one set of changes
sticks. With it, both are mutating the same object and the last commit wins
cleanly. The scope is the session — usually one HTTP request.
-->

---

# Identity Map — Sequence

<div class="diagram-fit">

```mermaid {scale: 0.7}
sequenceDiagram
    participant App as Application
    participant S as Session + Identity Map
    participant DB as Database

    App->>S: getUser(id = 42)
    S->>DB: SELECT * FROM users WHERE id = 42
    DB-->>S: row
    Note over S: cache User#42
    S-->>App: User#42

    App->>S: getUser(id = 42)  (again)
    Note right of S: cache hit — no SQL
    S-->>App: same User#42 instance
```

</div>

<!--
Emphasise "same instance", not "equal value". If the app mutated the first
object, the second lookup returns it with those mutations already in place —
because there is only one object.
-->

---

# Unit of Work

> Track every change in memory; flush them **all at once** in a single transaction.

<v-clicks>

- Object states: **New**, **Dirty**, **Clean**, **Deleted**
- On commit, the UoW emits `INSERT` / `UPDATE` / `DELETE` in a sensible order
- **Atomicity** — all succeed or all roll back
- **Batching** — fewer round-trips than writing per-object
- Lives inside the session / entity manager

</v-clicks>

<!--
This is why you can call session.add(...) ten times and see no SQL until
commit. The Unit of Work is the reason ORMs feel lazy about writes — and
it's why they can be atomic without you managing transactions explicitly.
-->

---

# Unit of Work — Sequence

<div class="diagram-fit">

```mermaid {scale: 0.7}
sequenceDiagram
    participant App as Application
    participant UoW as Unit of Work
    participant DB as Database

    App->>UoW: begin
    App->>UoW: create A       (New)
    App->>UoW: modify B       (Dirty)
    App->>UoW: delete C       (Deleted)
    App->>UoW: commit

    UoW->>DB: BEGIN
    UoW->>DB: INSERT A
    UoW->>DB: UPDATE B
    UoW->>DB: DELETE C
    UoW->>DB: COMMIT
    UoW-->>App: ok (or ROLLBACK on failure)
```

</div>

<!--
If any single statement fails, the ROLLBACK wipes the rest. Atomicity for
free, as long as you respect the session boundary. This pattern is what makes
"save the order with all its line items" feel like one operation.
-->

---

# The ORM-Pattern Landscape

| Pattern             | What it solves                       | Where you meet it                   |
|---------------------|--------------------------------------|-------------------------------------|
| Active Record       | Wiring a row to an object, fast      | Django models, Rails AR, Eloquent   |
| Data Mapper         | Isolating domain from persistence    | Hibernate entities, SQLA `Session`  |
| Repository          | Collection-shaped domain API         | Spring Data, EF Core, MikroORM      |
| Table Data Gateway  | Centralising a table's SQL           | DAOs, PHP persistence classes       |
| Row Data Gateway    | Row-level helpers without a full ORM | Legacy code, hand-rolled layers     |
| Lazy Loading        | Don't fetch what isn't used          | `fetch = LAZY`, `select_related`    |
| Identity Map        | One object per row, per session      | SQLA `Session`, Hibernate cache     |
| Unit of Work        | Batch changes, one transaction       | `session.commit()`, `em.flush()`    |

<!--
The "one slide to remember" table. Every one of these appears in the ORMs
students will meet in industry. If they can point at an ORM behaviour and
name the pattern, this section of the lecture has done its job.
-->

---
layout: section
---

# Schema Migrations

*Versioning the database alongside the code*

---

# Why Migrations?

Your code evolves. Your **schema** has to evolve with it — in every environment.

<v-clicks>

- Add a column today, ship the feature tomorrow, onboard a teammate next week
- Manual `ALTER TABLE` in production is how outages start
- Migrations are **version control for your schema**: ordered, scripted, reversible

</v-clicks>

<v-click>

> A migration is a **commit for your database**. If it's not in a migration, it didn't happen.

</v-click>

<!--
Motivation is the same as version control for source code: reproducibility
across environments and people. Treat migrations with the same respect: code
review them, don't edit them after they've shipped, don't skip them.
-->

---

# Migrations in Practice

| Framework          | Tool                        | Style                                |
|--------------------|-----------------------------|--------------------------------------|
| Django             | built-in `makemigrations`   | Auto-generated from model diffs      |
| Flask / SQLAlchemy | **Alembic**                 | Mostly manual, tracked with revisions|
| Ruby on Rails      | ActiveRecord migrations     | Ruby DSL, auto-generators            |
| Java / Hibernate   | **Flyway** or **Liquibase** | SQL or XML/YAML changesets           |
| Node / TypeORM     | TypeORM migrations          | TS/JS classes, `up()` / `down()`     |

<v-click>

All share the same idea: an **ordered list of versioned scripts** and a table in the database that remembers which ones have been applied.

</v-click>

<!--
Key insight: migrations are not a framework feature, they're a well-known
pattern. Even if you use raw SQL, you can roll your own migration runner in
a weekend — and sometimes you should.
-->

---

# Django Migration Example

```python
# app/migrations/0003_add_age_to_user.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0002_previous_migration_name'),
    ]
    operations = [
        migrations.AddField(
            model_name='user',
            name='age',
            field=models.IntegerField(null=True),
        ),
    ]
```

<v-click>

`python manage.py migrate` runs this file (and any others newer than the last applied). Django writes the `ALTER TABLE ... ADD COLUMN ...` for you and records `0003` as applied.

</v-click>

<!--
The dependency line is what makes the DAG hold together. Never edit a
migration after it's been applied in any environment — make a new one
instead. This is the "don't rewrite history" rule of database version control.
-->

---

# Zero-Downtime Migrations — Expand & Contract

Adding a required column to a live table in **one** step breaks the running app:
the old code doesn't know about it, the migration fails on existing rows.

<v-clicks>

The **expand / contract** pattern splits it in four:

1. **Expand** — add the column as *nullable* (deploy 1: schema change)
2. **Backfill** — write values to existing rows in batches
3. **Dual-write** — new code writes the column; old code ignores it
4. **Contract** — make the column `NOT NULL` and drop the old column (deploy 2)

</v-clicks>

<v-click>

> Ship the schema change and the code that needs it in **separate deploys**. Your database should never need the app to be down to evolve.

</v-click>

<!--
The canonical reference is Ambler & Sadalage's *Refactoring Databases* (2006).
The one rule students should leave with: `ALTER TABLE ... SET NOT NULL` on a
10-million-row table will take an `ACCESS EXCLUSIVE` lock. Schedule it
accordingly or use `NOT VALID` + `VALIDATE CONSTRAINT` in PostgreSQL.
-->

---

<div class="pg-trivia">
  <div class="pg-trivia-title">🐘 Postgres trivia · TOAST</div>
  <div class="pg-trivia-body">
    <strong>T</strong>he <strong>O</strong>versized-<strong>A</strong>ttribute <strong>S</strong>torage <strong>T</strong>echnique.
    PostgreSQL pages are 8 KB. When a <code>TEXT</code> or <code>JSONB</code> value doesn't fit, PostgreSQL silently
    moves it into a side table and compresses it. Your heap stays small, sequential scans stay fast, and you don't
    have to pick <code>VARCHAR(255)</code> defensively. Just use <code>TEXT</code>. PostgreSQL handles it.
  </div>
</div>

<v-click>

<div class="cool-tip">
  <div class="cool-tip-title">💡 Cool tip · partial indexes</div>
  Index only the rows you actually query:
  <code>CREATE INDEX ON orders (created_at) WHERE status = 'pending';</code><br/>
  The index is tiny, writes are cheap, and the planner uses it for matching queries.
</div>

</v-click>

<!--
TOAST is one of those features you only notice when it's absent — try storing
a 10 MB JSON blob in MySQL with default InnoDB row format. Partial indexes are
criminally underused; they pay for themselves the first time you need to find
"open tickets" in a table that's 99% closed tickets.
-->

---
layout: section
---

# The Deployment Ladder

*From your laptop to production, one rung at a time*

---

# Four Rungs, One Database Engine

A **rung** is one step on a ladder. We climb from "the database on my laptop" to "the database someone else runs for me" — the **engine** is the same PostgreSQL binary at every step; what changes is **who operates it**.

<div class="mt-5 space-y-2 text-sm">

<div class="flex items-center gap-4 p-3 border-l-4 border-sky-500 bg-sky-50 rounded">
  <div class="font-mono font-semibold w-28 shrink-0">☁️ Rung 3</div>
  <div class="flex-1"><strong>Managed SaaS</strong> — RDS / Cloud SQL / Neon / Supabase. Someone else carries the pager.</div>
</div>

<div class="flex items-center gap-4 p-3 border-l-4 border-indigo-500 bg-indigo-50 rounded">
  <div class="font-mono font-semibold w-28 shrink-0">☸️ Rung 2</div>
  <div class="flex-1"><strong>On-prem Kubernetes</strong> — CloudNativePG operator, or a classic VM + Patroni.</div>
</div>

<div class="flex items-center gap-4 p-3 border-l-4 border-blue-400 bg-blue-50 rounded">
  <div class="font-mono font-semibold w-28 shrink-0">🐳 Rung 1</div>
  <div class="flex-1"><strong>Docker Compose</strong> — local dev, CI, and "emulate prod on a laptop."</div>
</div>

<div class="flex items-center gap-4 p-3 border-l-4 border-gray-400 bg-gray-50 rounded">
  <div class="font-mono font-semibold w-28 shrink-0">🧑‍💻 Rung 0</div>
  <div class="flex-1"><strong><code>psql</code> on your laptop</strong> — zero abstraction, you are the DBA.</div>
</div>

</div>

<v-click>

> **Climb up**: less toil, more cost, more lock-in. **Climb down**: more control, more responsibility at 3 a.m. Pick the highest rung your compliance, cost, and sovereignty allow.

</v-click>

<!--
The rung metaphor is deliberate: a ladder is vertical, rungs are ordered, and
you can stand on any of them. Nobody climbs the whole thing — you pick a rung
for the production workload and use Rung 0 and Rung 1 for dev. The engine
being the same Postgres binary at every level is the unifying thread.
-->


<!--
Frame this as a ladder, not a hierarchy. Rung 3 is not "better than" Rung 0 —
it's just "where you pay someone else to carry the pager." Reasonable teams
live on different rungs depending on regulatory posture, budget, and scale.
-->

---

# Rung 0 — `psql` on Your Laptop

```bash
brew install postgresql@17          # macOS
sudo apt install postgresql-17      # Debian/Ubuntu

createdb awesome_database
psql awesome_database
```

<v-clicks>

- Zero abstraction — you are the DBA
- Perfect for scripting, learning, exploration
- Painful when the project needs a different PostgreSQL version than your system
- Doesn't survive a laptop wipe unless you remember to `pg_dump`

</v-clicks>

<v-click>

> Every developer should be comfortable at Rung 0. You can't debug Rung 3 if you can't read `\d+` output.

</v-click>

<!--
Don't skip this rung. Students who never touch raw psql end up unable to
introspect their ORM-generated schemas. Teach the basics: \d, \d+, \l,
\dt, \df, \c. They're the stethoscope of database work.
-->

---

# Rung 1 — Docker Compose

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:17
    container_name: myapp_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: arthur
      POSTGRES_PASSWORD: krikkit
      POSTGRES_DB: awesome_database
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
volumes:
  db_data:
```

<!--
Compose resolves service names as hostnames on the internal network — that's
why the app uses PGHOST=db. From the host machine you'd use localhost:5432
instead, because of the ports map. The volume survives container restarts;
remove it on purpose when you want a clean slate.
-->

---

# Rung 1 — Why Docker for Dev

<v-clicks>

- **Reproducible** — everyone runs the same PostgreSQL 17
- **Disposable** — `docker compose down -v` wipes it clean
- **Parallel** — Postgres 14 for one project, 17 for another, no global conflict
- **Closer to prod** — the same image runs in CI, staging, and (maybe) production
- **Pairs with env vars** — the twelve-factor config story

</v-clicks>

<v-click>

> Rung 1 is your **local development** rung. It is not — by itself — a production strategy.

</v-click>

<!--
Docker Compose for the database is great for dev and CI. It's NOT a production
strategy because it does not solve: backups, HA, rolling upgrades, TLS
termination, connection pooling, or monitoring. People who ran a single
container in prod "for years" are the same people who later say "we got
lucky." Don't be that team.
-->

---

# Rung 2 — On-Prem Kubernetes

You run the nodes. Something has to turn "PostgreSQL" into a highly-available, self-healing Kubernetes workload.

<v-clicks>

- **CloudNativePG** (CNPG) — the de-facto open-source operator, CNCF sandbox
- A `Cluster` CRD declares: "3 replicas of Postgres 17, 100 GB, backups to S3"
- Operator handles failover, rolling upgrades, backups, monitoring integration
- Alternatives: **Zalando Postgres Operator**, **Crunchy PGO**
- **Legacy bridge: Patroni + streaming replication** on VMs is still widespread
  — DCS-based leader election, same concepts CNPG hides behind the CRD

</v-clicks>

<!--
Explain Patroni even though it's a single bullet: Patroni is a Python HA
template that runs as a sidecar on each Postgres node, uses a Distributed
Configuration Store (etcd, Consul, Kubernetes) to coordinate leader election.
Exactly one node at a time holds the leader lock; others stream-replicate
from it. On lease expiry, a follower promotes itself and updates routing
(HAProxy / PgBouncer / virtual IP). The "magic" is just streaming replication
+ a lease with a TTL + a supervisor watching both. CloudNativePG replaces
this with K8s primitives: the CRD is the lease, the StatefulSet is the nodes,
the operator is Patroni. Naming Patroni bridges the "VMs + scripts" era that
internships still use and the operator era everything else covers.
-->

---

# Rung 2 — CloudNativePG Cluster

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: awesome-cluster
spec:
  instances: 3
  postgresql:
    parameters:
      shared_buffers: 256MB
      max_connections: "200"
  storage:
    size: 100Gi
    storageClass: fast-ssd
  backup:
    barmanObjectStore:
      destinationPath: s3://backups/awesome
      s3Credentials:
        accessKeyId: { name: s3-creds, key: ACCESS_KEY_ID }
        secretAccessKey: { name: s3-creds, key: SECRET_ACCESS_KEY }
    retentionPolicy: "30d"
```

<!--
One YAML, three replicas, automatic failover, continuous backups to S3, 30-day
retention. This replaces what used to be two weeks of runbook-writing. The
operator watches the CRD and reconciles until reality matches the spec —
that's the Kubernetes pattern, applied to PostgreSQL.
-->

---

# Rung 3 — Managed SaaS

You stop running PostgreSQL and start *using* it. The provider's SRE team carries the pager.

<div class="grid grid-cols-5 gap-4 mt-6 text-sm">
<div class="text-center">
  <div class="font-semibold">RDS / Aurora</div>
  <div class="opacity-70 mt-1">AWS<br/>The default in industry</div>
</div>
<div class="text-center">
  <div class="font-semibold">Cloud SQL</div>
  <div class="opacity-70 mt-1">Google Cloud<br/>Tight GCP integration</div>
</div>
<div class="text-center">
  <div class="font-semibold">Azure DB</div>
  <div class="opacity-70 mt-1">Microsoft Azure<br/>AD identity-aware</div>
</div>
<div class="text-center">
  <div class="font-semibold">Neon</div>
  <div class="opacity-70 mt-1">Serverless Postgres<br/>Branching like git</div>
</div>
<div class="text-center">
  <div class="font-semibold">Supabase</div>
  <div class="opacity-70 mt-1">Postgres + REST API<br/>+ auth, out of the box</div>
</div>
</div>

<v-click class="mt-6">

> The cheap price of a managed DB is not the bill. It's the **lock-in and the egress cost** when you try to leave.

</v-click>

<!--
Five providers worth naming. RDS/Aurora for incumbent weight, Cloud SQL and
Azure DB for their respective ecosystems, Neon for serverless + branching
(huge for CI), Supabase as the "Postgres-as-platform" story (PostgREST + Auth
layered on top, RLS-enforced). Crunchy Bridge stays in speaker notes only.
Don't spend more than one sentence on Supabase on slide — it's a provider,
not a curriculum.
-->

---

# Choosing Your Rung

<v-clicks>

1. **Regulated data** or **sovereign-cloud** requirement? → **Rung 2** (on-prem K8s)
2. No regulatory constraint, **small team** (< 3 SREs)? → **Rung 3** (managed SaaS)
3. Large team, **cost-sensitive at scale**? → **Rung 2** pays back the SRE investment
4. Everyone else? → **Rung 3** — paying for someone else's pager is almost always cheaper than carrying it

</v-clicks>

<v-click>

Whichever you pick for production, use **Rung 1 (Docker Compose)** for local dev from day one, and keep **Rung 0 (`psql`)** sharp for debugging.

</v-click>

<v-click>

> Most teams should start at **Rung 3** and only descend to **Rung 2** when compliance, cost, or sovereignty forces the hand.

</v-click>

<!--
Decision rules, not a tree diagram — trees with eight arrows and five boxes
stop being helpful. The real answer is cultural: teams with SRE maturity can
absorb Rung 2, teams without will burn out trying. Student takeaway: when
you join a company, find out which rung they're on and why.
-->


<!--
Decision-tree shape, but the real answer is cultural. Teams with SRE maturity
can absorb Rung 2; teams without will burn out trying. Student takeaway: when
you join a company, find out which rung they're on and why.
-->

---

# Connecting from Node.js

```javascript
import { Client } from 'pg'

const client = new Client({
  host:     process.env.PGHOST     ?? 'localhost',
  port:     Number(process.env.PGPORT ?? 5432),
  database: process.env.PGDATABASE,
  user:     process.env.PGUSER,
  password: process.env.PGPASSWORD,
})

try {
  await client.connect()
  const { rows } = await client.query(
    'SELECT id, name FROM users WHERE id = $1', [userId]   // parameterised
  )
  console.log(rows[0])
} finally {
  await client.end()
}
```

<!--
Notice $1 — the parameter is sent separately from the SQL text. That's not
style, it's the defence against SQL injection we'll see live in a few slides.
The pg library will also auto-read PG* env vars if you pass no config at all
— same story at every rung of the ladder.
-->

---

# Connecting from Python (`psycopg` 3)

```python
import os, psycopg

with psycopg.connect(
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", 5432)),
    dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name FROM users WHERE name = %s",   # parameterised
            ("Alice",),
        )
        for row in cur.fetchall():
            print(row)
```

<v-click>

Same shape as Node, at every rung: **read env vars, parameterise queries, let the context manager clean up.**

</v-click>

<!--
psycopg 3's %s is *its* placeholder — not Python % formatting. The trailing
comma in ("Alice",) is required to make a tuple. Context managers handle
commit/rollback and close — exactly what you want in production code.
-->

---
layout: section
---

# Operations

*Pooling, observability, backups — keeping it alive at 3 a.m.*

---

# The Connection Pooling Problem

<v-clicks>

- A PostgreSQL connection costs ~10 MB RAM and a backend process
- `max_connections` defaults to **100**. That's it.
- 100 app pods × 20 connections each = **2000 connections requested** → ⚠️
- Connections are expensive to open, cheap to reuse

</v-clicks>

<v-click>

> The answer is a **connection pooler** — one in front of your database that multiplexes many client connections onto few server connections.

</v-click>

<!--
This is the #1 reason a happy-path app dies under load. Default PostgreSQL
caps out at 100 connections, and each of those is a forked backend process.
Without a pooler, a few dozen app instances will exhaust connections before
they exhaust anything else. This slide earns its keep the first time a
student's deployed app falls over at 150 concurrent users.
-->

---

# PgBouncer — Pooling Modes

Many cheap app connections funnel into few expensive Postgres backends.

| Mode         | Server connection held for… | Good for                 | Breaks…                       |
|--------------|-----------------------------|--------------------------|-------------------------------|
| Session      | the client's full session   | Safe default             | Little (but no sharing)       |
| Transaction  | one transaction             | Web apps, REST APIs      | Session-level `SET`, `LISTEN` |
| Statement    | one statement               | Extreme multiplexing     | Multi-statement transactions  |

<v-click>

> **Transaction pooling** is the sweet spot for stateless web apps. It's also the mode most people enable without reading the docs and break their `SET search_path` with.

</v-click>

<!--
PgBouncer is boring, stable, and the default. pgcat is a newer Rust
alternative with sharding built in — note it exists, don't depend on it in
week one. Odyssey is Yandex's production-tested alternative. The pooling-mode
table is the thing worth memorising.
-->

---

# Observability — `pg_stat_statements`

A built-in extension that records every query's aggregated stats.

```sql
CREATE EXTENSION pg_stat_statements;

SELECT queryid, calls, mean_exec_time, total_exec_time, rows, query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

<v-clicks>

- Shows you the **top-N queries by total cost** across the whole server
- Normalises `WHERE id = 42` and `WHERE id = 99` into the same entry
- First install in any new PostgreSQL cluster — no exceptions
- Usually enabled by default on managed SaaS

</v-clicks>

<!--
If a student takes ONE thing away from the operations section, it's this
extension. Every performance complaint in a real job starts with "which query
is slow?" and pg_stat_statements answers that question in five seconds. The
alternative is log scraping, which is painful, or DBA mysticism, which is
worse.
-->

---

# Observability — The Full Stack

<div class="diagram-fit">

```mermaid {scale: 0.7}
flowchart LR
    PG[(PostgreSQL)]
    PG --> E[postgres_exporter]
    PG -.slow log.-> L[Loki / stdout]
    E --> P[Prometheus]
    L --> G[Grafana]
    P --> G
    G --> A["alerts<br/>replication lag · deadlocks<br/>cache hit ratio · long queries"]
```

</div>

<v-clicks>

- `postgres_exporter` — scrapes `pg_stat_*` views into Prometheus metrics
- Slow-query log — set `log_min_duration_statement = 500` to log anything over 500 ms
- Grafana dashboard — the community one (12485) is a sane starting point

</v-clicks>

<!--
You don't have to build this yourself. Most managed providers hand you a
pre-built dashboard. On Rung 2 with CloudNativePG, the operator exposes
metrics on a sidecar out of the box. The mental model matters more than the
stack: metrics for rates and saturation, logs for individual incidents,
traces for request attribution.
-->

---

# Backups — The 3-2-1 Rule

<v-clicks>

- **3** copies of your data
- on **2** different media
- with **1** copy off-site

</v-clicks>

<v-click>

**For PostgreSQL, concretely:**

- `pg_dump` — logical, per-database, portable, slow for huge DBs
- `pg_basebackup` + WAL archiving — physical, fast, **Point-in-Time Recovery**
- **pgBackRest** or **WAL-G** — production-grade WAL-archive-aware tools

</v-click>

<v-click>

> An **untested backup is a rumour**. Schedule a restore drill. If you don't restore to a scratch instance once a quarter, you don't have backups — you have hope.

</v-click>

<!--
The 3-2-1 rule is from storage engineering generally, not PostgreSQL
specifically. PITR is the killer feature: "restore the database to 14:37 last
Tuesday" is the difference between a bad afternoon and a company-ending
outage. Rehearse the restore. Every team that has never restored from backup
is one DROP TABLE away from finding out their backups don't work.
-->

---

# Health Checks

<v-clicks>

- **Liveness** — "is the Postgres process running?" — `pg_isready` is enough
- **Readiness** — "is the database *actually serving*?" — much harder
- A Postgres that's recovering WAL after a crash is **live but not ready**
- A follower that's lagging 30 minutes is **ready** for reads but **not** for your app's consistency needs

</v-clicks>

<v-click>

> A good readiness probe runs a cheap real query (`SELECT 1`) **and** checks replication lag **and** checks there's at least one usable connection in the pool. Three conditions, not one.

</v-click>

<!--
This is where Kubernetes learners trip up. `pg_isready` answers "is the
listener accepting TCP?" which is not the same as "is the database ready to
serve your app." CloudNativePG gets this right out of the box; hand-rolled
StatefulSets usually don't.
-->

---

<div class="pg-trivia">
  <div class="pg-trivia-title">🐘 Postgres trivia · <code>EXPLAIN (ANALYZE, BUFFERS)</code></div>
  <div class="pg-trivia-body">
    The single most useful four words in PostgreSQL. Prefix any <code>SELECT</code> / <code>UPDATE</code> /
    <code>INSERT</code> / <code>DELETE</code> to see the planner's chosen plan, the row estimates, the actual rows,
    and the page reads (<code>BUFFERS</code>). When the estimate and actual diverge by 10×, that's where your slow
    query lives. When <code>shared read</code> is high, your cache is cold. <strong>Always</strong> send this
    output, never a plain <code>EXPLAIN</code>, in a slow-query ticket.
  </div>
</div>

<v-click>

<div class="cool-tip">
  <div class="cool-tip-title">💡 Cool tip · extensions worth knowing</div>
  <code>pgvector</code> (embeddings / RAG), <code>PostGIS</code> (geospatial), <code>pg_trgm</code> (fuzzy text search),
  <code>pgcrypto</code> (hashing, UUIDs), <code>timescaledb</code> (time-series). PostgreSQL's extension system is
  the reason so many "purpose-built" databases are "PostgreSQL with two extensions" under the hood.
</div>

</v-click>

<!--
EXPLAIN ANALYZE BUFFERS is genuinely life-changing once you get fluent with
it. Teach students to read the leaves first (which tables, what access method,
row estimates) and work up. Extensions are why PostgreSQL is the answer to
"which database should I use in 2026" 80% of the time.
-->

---
layout: section
---

# Security

*Injection (live!), secrets, TLS, row-level security*

---

# SQL Injection — The Risk

```python
# DO NOT DO THIS
name  = request.GET['username']
query = f"SELECT * FROM users WHERE username = '{name}'"
cursor.execute(query)
```

<v-click>

An attacker sends `name = Alice' OR '1'='1` and your query becomes:

```sql
SELECT * FROM users WHERE username = 'Alice' OR '1'='1'
```

</v-click>

<v-click>

The `OR '1'='1'` tautology matches every row. Login bypassed. Entire table leaked.

</v-click>

<v-click>

> Still the **#1 web vulnerability** on the OWASP Top Ten — because people still write this code in 2026.

</v-click>

<!--
Resist the temptation to "just escape quotes." Manual escaping is famous for
being subtly wrong. Parameterised queries make the whole class of attack
structurally impossible — which is a much better property than "I think I
escaped everything."
-->

---

# Prevention — Prepared Statements

> Send the SQL and the values **separately**. The database never mixes data into code.

<div class="grid grid-cols-2 gap-6">
<div>

**Java / JDBC**

```java
PreparedStatement ps = conn.prepareStatement(
    "SELECT * FROM users WHERE username = ?"
);
ps.setString(1, userInput);
ResultSet rs = ps.executeQuery();
```

</div>
<div>

**Python / psycopg**

```python
cur.execute(
    "SELECT * FROM users WHERE username = %s",
    (user_input,),
)
```

</div>
</div>

<v-click>

ORMs do this **for you** — `User.objects.filter(username=user_input)` in Django parameterises under the hood. **The moment you reach for string concatenation, stop.**

</v-click>

<!--
The rule is absolute: if you're concatenating user input into a SQL string,
you have a bug. The edge case is dynamic SQL (ORDER BY, column names) which
parameters don't cover — that needs an allow-list approach, never raw
concatenation. Flag that in notes.
-->

---

# Meet Little Bobby Tables

<div class="flex justify-center mt-4">
  <img src="https://imgs.xkcd.com/comics/exploits_of_a_mom.png" class="rounded shadow-md max-h-80" />
</div>

<div class="text-xs opacity-40 mt-3 text-center">

Source: [xkcd #327 — Exploits of a Mom](https://xkcd.com/327/) by Randall Munroe (CC BY-NC 2.5)

</div>

<!--
The most famous database joke of all time. If you remember one thing from this
lecture, let it be: "sanitise your database inputs." Parameterised queries
are how. The comic is twenty years old. We're still fighting this.
-->

---

# Secrets Management

Hardcoding `POSTGRES_PASSWORD: krikkit` in `docker-compose.yml` is fine for learning. For anything real, you need a **secrets manager**.

<v-clicks>

- **HashiCorp Vault** — the classic; dynamic database credentials, short-lived
- **Cloud-native managers** — AWS Secrets Manager, GCP Secret Manager, Azure Key Vault
- **External Secrets Operator** — Kubernetes operator that syncs secrets from any of the above into `Secret` resources
- **SOPS** — encrypt secrets in git using KMS / age keys (good for GitOps)

</v-clicks>

<v-click>

> **Never** commit a `.env` with real credentials. **Never** put secrets in container environment variables that show up in `docker inspect` output. **Always** rotate on any suspicion of leak.

</v-click>

<!--
If the student goes home with one rule: secrets don't live in git. Dynamic
credentials from Vault are the gold standard — the application gets a new
short-lived password on every startup and never sees a long-lived one.
External Secrets Operator is the K8s-friendly way to bridge cloud secret
managers into your pods without copy-paste.
-->

---

# TLS on the Wire

```
postgresql://user:password@db.example.com:5432/app?sslmode=verify-full
```

<v-clicks>

- `sslmode=disable` — 💀 plaintext, **never** across a network
- `sslmode=require` — encrypts, but does NOT verify the server's identity
- `sslmode=verify-ca` — verifies the CA, not the hostname
- `sslmode=verify-full` — verifies CA **and** hostname — the only correct choice for the internet

</v-clicks>

<v-click>

> Managed providers default to TLS. Self-hosted often defaults to `prefer`, which silently falls back to plaintext. **Audit the mode** — don't trust the default.

</v-click>

<!--
This is an easy one to miss in a lab environment where everything is
localhost. In production the difference between verify-full and require is
"I can be MITMed" vs "I can't." Managed SaaS providers get this right;
self-hosted often doesn't.
-->

---

# Row-Level Security

PostgreSQL has **per-row** access control built in, since 9.5 (2016).

```sql
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON orders
  USING (tenant_id = current_setting('app.current_tenant')::int);

-- in your app connection pool, at the start of each request:
SET app.current_tenant = '42';

SELECT * FROM orders;  -- only returns orders where tenant_id = 42
```

<v-click>

> This is how Supabase makes a raw Postgres schema safe to expose as a public API. The database enforces the filter, so even a compromised client can't see other tenants' data.

</v-click>

<!--
RLS is one of those features that seems niche until you need it, at which
point nothing else works. Multi-tenant SaaS, per-user data partitioning,
regulatory isolation — all of it becomes trivial with RLS and a connection
setting. The cost is careful policy design; the reward is defence in depth
that no application bug can bypass.
-->

---

# Beyond Injection — Security Checklist

<v-clicks>

- **Least privilege** — the app's DB user can `SELECT`/`INSERT`/`UPDATE` what it needs, nothing more
- **Secrets stay out of git** — Vault / ESO / SOPS / cloud managers
- **TLS verify-full** — mandatory off-localhost
- **Row-Level Security** — where the data model justifies it
- **Backups** — tested, restorable, off-site
- **Patches** — keep server, drivers, and ORM current
- **Monitor & log** — anomalous query patterns are often the first sign of an incident
- **Input validation** — not a replacement for parameterisation, but a useful second line

</v-clicks>

<v-click>

> Defence in depth: prepared statements alone are not a security strategy, they're the **floor**.

</v-click>

<!--
Most real-world database incidents are more boring than injection: a leaked
password in a repo, an open port on a staging box, an over-privileged service
account. Treat the whole stack as part of "database security."
-->

---
layout: section
---

# Practical Examples

*Same idea, three languages* 🐍 ☕

---

# Django — Active Record in Python

```python
from django.db import models

class Author(models.Model):
    name  = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

class Book(models.Model):
    title            = models.CharField(max_length=200)
    publication_date = models.DateField()
    author           = models.ForeignKey(
        Author, on_delete=models.CASCADE, related_name='books'
    )
```

<!--
Django feels the most "batteries included" of the three. One class produces a
model, a migration, an admin page, a form. The ergonomics are great for CRUD
apps and admin dashboards; less great when domain behaviour doesn't belong
on a row.
-->

---

# Django — Usage

```python
author = Author.objects.create(
    name="George Orwell",
    email="orwell@example.com",
)

Book.objects.create(
    title="1984",
    publication_date="1949-06-08",
    author=author,
)

# Reverse relation via related_name='books'
for book in author.books.all():
    print(book.title)

# Eager-load to avoid N+1
Book.objects.select_related("author").filter(publication_date__year=1949)
```

<!--
Note .create() returns a saved instance. select_related for ForeignKey to
join eagerly; prefetch_related for reverse FK / M2M. Those two verbs plus the
__ double-underscore filter syntax will carry students a long way.
-->

---

# SQLAlchemy — Data Mapper in Python

```python
from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Author(Base):
    __tablename__ = 'authors'
    id    = Column(Integer, primary_key=True)
    name  = Column(String(100))
    email = Column(String(100), unique=True)
    books = relationship("Book", back_populates="author")

class Book(Base):
    __tablename__ = 'books'
    id               = Column(Integer, primary_key=True)
    title            = Column(String(200))
    publication_date = Column(Date)
    author_id        = Column(Integer, ForeignKey('authors.id', ondelete="CASCADE"))
    author           = relationship("Author", back_populates="books")
```

<!--
No save() on the classes. The Session (next slide) is where persistence
happens. back_populates keeps both sides of the relationship in sync in
memory when you mutate either side.
-->

---

# SQLAlchemy — Usage

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine  = create_engine("postgresql://user:pass@localhost/mydb")
Session = sessionmaker(bind=engine)

with Session() as session:
    orwell = Author(name="George Orwell", email="orwell@example.com")
    Book(title="Animal Farm", publication_date="1945-08-17", author=orwell)
    session.add(orwell)
    session.commit()          # one transaction: INSERT author, INSERT book
```

<v-click>

The Session is Data Mapper + Identity Map + Unit of Work in one object. Nothing hits the database until `commit()`.

</v-click>

<!--
This one slide is where the three patterns we named earlier all show up in
one piece of code. Point at session.add (UoW: "New"), point at the implicit
relationship cascade (the Book gets persisted because it's reachable from the
tracked Author), point at the transaction boundary (commit).
-->

---

# Hibernate — Data Mapper in Java

```java
@Entity
@Table(name = "authors")
public class Author {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;

    @Column(unique = true)
    private String email;

    @OneToMany(mappedBy = "author", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Book> books = new ArrayList<>();
}
```

<!--
Java verbosity makes the pattern obvious: lots of annotations, no persistence
code on the entity. Skip the EntityManagerFactory setup; students know what
it looks like from other Java courses.
-->

---

# Hibernate — Usage

```java
EntityManager em = emf.createEntityManager();
em.getTransaction().begin();

Author a = new Author();
a.setName("Agatha Christie");
a.setEmail("agatha@example.com");
em.persist(a);                 // tracked as New

em.getTransaction().commit();  // Unit of Work flushes the INSERT
```

<v-click>

Same pattern as SQLAlchemy: `EntityManager` = Mapper + Identity Map + Unit of Work.

</v-click>

<!--
Common pitfall worth flagging: if you also create a Book and do
book.setAuthor(a), remember to a.getBooks().add(book) so both sides of the
relationship agree in memory. Hibernate doesn't do this for you on the set
path, only on load.
-->

---
layout: section
---

# Quizzes

*Quick sanity checks* 🧠

---

# Quiz 1 — Active Record or Data Mapper?

You are building a small blog by yourself. You want quick iteration, simple CRUD, minimal ceremony. Complex business logic is unlikely.

**Which pattern fits, and why?**

<v-click>

> **Active Record.** You want `post.save()` and to be done. Data Mapper's session / unit-of-work overhead is justified when you have real domain behaviour to protect from the database — you don't, yet. Django or Rails will get you shipping in an afternoon.

</v-click>

<!--
The point: pattern choice is a trade-off, not a truth. For a solo CRUD app,
the "simpler, more coupled" option is genuinely correct. Push back on
students who overcorrect towards enterprise patterns.
-->

---

# Quiz 2 — Spot the Performance Bug

```python
posts = Post.objects.all()              # 100 posts
for post in posts:
    print(post.title)
    print("Comments:", len(post.comments.all()))
```

<v-click>

> **N+1 query problem.** One query fetches the posts; each `post.comments.all()` fires another. That's 1 + 100 = **101 queries** for one page.

</v-click>

<v-click>

**Fix** — eager-load in a single prefetch:

```python
Post.objects.all().prefetch_related('comments')   # 2 queries, regardless of N
```

</v-click>

<!--
Extremely common in the wild. Every ORM has a toolbox for eager loading;
learn the verbs (select_related, prefetch_related, joinedload, JOIN FETCH)
for whichever ORM you're using.
-->

---

# Quiz 3 — Spot the Security Bug

```javascript
app.get("/users", (req, res) => {
  const search = req.query.name
  db.query(
    `SELECT * FROM users WHERE name = '${search}'`,
    (err, result) => res.json(result.rows)
  )
})
```

<v-click>

> **SQL injection.** `?name=bob' OR '1'='1` leaks every user. `?name=x'; DROP TABLE users; --` is worse.

</v-click>

<v-click>

**Fix** — parameterise:

```javascript
db.query(
  "SELECT * FROM users WHERE name = $1",
  [search],
  (err, result) => res.json(result.rows),
)
```

</v-click>

<!--
If a student ever concatenates user input into SQL in your code review, push
back hard. It's rarely "just this once" — the pattern metastasises.
-->

---

# Quiz 4 — Spot the Deployment Mistake

```yaml
# production k8s manifest
env:
  - name: PGHOST
    value: db.prod.internal
  - name: PGPASSWORD
    value: "hunter2-prod-admin"             # (1)
  - name: PGSSLMODE
    value: "disable"                         # (2)
- run: kubectl exec -it postgres-0 -- psql -c "ALTER TABLE users ADD COLUMN age INT NOT NULL"
                                             # (3)
```

<v-click>

> **Three mistakes** — can you name them?

</v-click>

<v-clicks>

1. 💀 Hardcoded password in the manifest (commit this and it's in git forever)
2. 💀 `sslmode=disable` over a network (MITM-able, plaintext credentials)
3. 💀 Manual `ALTER TABLE` outside migrations, **and** `NOT NULL` without a default on a live table (will lock the table for the duration of the backfill)

</v-clicks>

<!--
One question, three lessons from three different sections of the lecture.
This quiz is the callback quiz — secrets, TLS, migrations — all the
application-aspects concerns in one YAML.
-->

---
layout: section
---

# Summary

---

# What We Covered Today

<v-clicks>

1. **ORMs** are a stack of patterns — Active Record, Data Mapper, Gateways, Lazy Loading, Identity Map, Unit of Work
2. **Migrations** are version control for your schema — expand/contract for zero-downtime
3. **The Deployment Ladder** — laptop → Docker → Kubernetes + CloudNativePG → managed SaaS
4. **Operations** — pool with PgBouncer, observe with `pg_stat_statements`, back up with the 3-2-1 rule
5. **Security** — prepared statements (always), secrets out of git, TLS verify-full, RLS where it fits
6. **ORMs are a layer, not a wall** — read the SQL, watch for N+1, own your schema

</v-clicks>

<v-click>

> *"An ORM makes the easy things easy and the hard things visible."*

</v-click>

<!--
One slide, one map of the lecture. Students should leave able to name the
patterns, recognise them in code, and reach for the right tool when they hit
the matching problem.
-->

---

# What's Next?

<v-clicks>

- **Transactions & isolation levels** — what *actually* happens inside `BEGIN` / `COMMIT`
- **Connection pooling deep-dive** — transaction pooling pitfalls, prepared-statement caches
- **Caching strategies** — Redis, materialised views, query-result caches
- **Observability deep-dive** — traces, spans, slow-query attribution
- **Sharding & replication** — when one Postgres isn't enough

</v-clicks>

<v-click>

> Today was the *what*. The next lectures dig into the *why it's fast* and *why it's correct under load*.

</v-click>

<!--
Plant the hooks for the rest of the semester. Application aspects is a broad
topic — this lecture is the foundation later lectures build on.
-->

---

# Further Reading

<div class="grid grid-cols-2 gap-x-8 gap-y-3 text-sm mt-4">

<div>

**Canon — relational & design**

- Codd, E. F. (1970). *A Relational Model of Data for Large Shared Data Banks*. CACM 13(6). [DOI](https://doi.org/10.1145/362384.362685) →
- Chen, P. P. (1976). *The Entity-Relationship Model*. ACM TODS 1(1). [DOI](https://doi.org/10.1145/320434.320440) →
- Stonebraker, M. & Rowe, L. A. (1986). *The Design of POSTGRES*. SIGMOD. [DOI](https://doi.org/10.1145/16856.16888) →
- Gray, J. (1981). *The Transaction Concept*. VLDB.

</div>

<div>

**Patterns & engineering**

- Fowler, M. (2003). *Patterns of Enterprise Application Architecture*. Addison-Wesley.
- Evans, E. (2003). *Domain-Driven Design*. Addison-Wesley.
- Ambler, S. & Sadalage, P. (2006). *Refactoring Databases*. Addison-Wesley.
- Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly.

</div>

<div>

**Docs & standards**

- PostgreSQL 17 Documentation — [postgresql.org/docs/17](https://www.postgresql.org/docs/17/) →
- OWASP Top Ten — [owasp.org/www-project-top-ten](https://owasp.org/www-project-top-ten/) →

</div>

<div>

**Going operational**

- CloudNativePG — [cloudnative-pg.io](https://cloudnative-pg.io/) →
- PgBouncer docs — [pgbouncer.org](https://www.pgbouncer.org/) →
- pgBackRest — [pgbackrest.org](https://pgbackrest.org/) →
- Supabase architecture — [supabase.com/docs](https://supabase.com/docs/) →

</div>

</div>

<!--
Photograph this slide if you want it offline — the whole point of the reading
list is that it outlives the lecture. The left column is the canon, right is
the modern ops stack. Helland's "Life beyond Distributed Transactions" and
Sadalage & Fowler's "NoSQL Distilled" are worth naming if anyone asks.
-->

---
layout: center
class: text-center
---

# Questions? 🙋

<div class="text-lg opacity-60 mt-2">Application Aspects in Database Systems</div>

<div class="mt-8 text-sm opacity-50">

*"An ORM makes the easy things easy and the hard things visible."*

</div>

<div class="mt-8">
  <img src="/images/logo_fiit.svg" class="h-8 inline-block" alt="FIIT STU" />
</div>

<div class="text-sm opacity-40 mt-4">
Jakub Dubec — Database Systems 2026
</div>
