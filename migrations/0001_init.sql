-- Morning Edition story tracking schema
-- Apply manually via the Supabase SQL editor.

create table editions (
  date          date primary key,
  fetched_at    timestamptz,
  published_at  timestamptz,
  commit_sha    text
);

create table stories (
  id              bigserial primary key,
  edition_date    date not null references editions(date) on delete cascade,
  status          text not null check (status in ('published','rejected')),
  source          text not null check (source in ('hn','pinboard')),
  rank            int,
  url             text not null,
  title           text not null,
  category        text,
  applies         boolean,
  byline          text,
  blurb           text,
  hn_link         text,
  hn_id           bigint,
  hn_score        int,
  hn_comments     int,
  hn_author       text,
  pb_tags         text[],
  pb_description  text,
  unique (edition_date, url),
  check (status = 'published' or rank is null),
  check (status = 'rejected' or rank is not null)
);

create index stories_status_date_idx on stories (status, edition_date desc);
create index stories_source_date_idx on stories (source, edition_date desc);
create index stories_pb_tags_idx on stories using gin (pb_tags);
