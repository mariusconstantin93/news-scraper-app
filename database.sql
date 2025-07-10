--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

-- Started on 2025-07-11 01:59:53

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE IF EXISTS news_scraper_db;
--
-- TOC entry 5081 (class 1262 OID 16387)
-- Name: news_scraper_db; Type: DATABASE; Schema: -; Owner: postgres
--

CREATE DATABASE news_scraper_db WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'English_United States.1252';


ALTER DATABASE news_scraper_db OWNER TO postgres;

\connect news_scraper_db

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 4 (class 3079 OID 16673)
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- TOC entry 5082 (class 0 OID 0)
-- Dependencies: 4
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- TOC entry 3 (class 3079 OID 16482)
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- TOC entry 5083 (class 0 OID 0)
-- Dependencies: 3
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- TOC entry 2 (class 3079 OID 16471)
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- TOC entry 5084 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- TOC entry 296 (class 1255 OID 17368)
-- Name: generate_content_hash(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.generate_content_hash() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.content_hash := encode(
        digest(CONCAT(COALESCE(NEW.title, ''), COALESCE(NEW.summary, ''), COALESCE(NEW.link, '')), 'sha256'), 
        'hex'
    );
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.generate_content_hash() OWNER TO postgres;

--
-- TOC entry 302 (class 1255 OID 17750)
-- Name: get_advanced_stats(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_advanced_stats() RETURNS TABLE(metric_name character varying, metric_value numeric, metric_unit character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'total_articles'::VARCHAR as metric_name,
        (SELECT COUNT(*)::NUMERIC FROM news_articles) as metric_value,
        'count'::VARCHAR as metric_unit
    UNION ALL
    SELECT 
        'active_sources'::VARCHAR as metric_name,
        (SELECT COUNT(DISTINCT source)::NUMERIC FROM news_articles) as metric_value,
        'count'::VARCHAR as metric_unit
    UNION ALL
    SELECT 
        'articles_today'::VARCHAR as metric_name,
        (SELECT COUNT(*)::NUMERIC FROM news_articles WHERE timestamp >= CURRENT_DATE) as metric_value,
        'count'::VARCHAR as metric_unit
    UNION ALL
    SELECT 
        'articles_last_week'::VARCHAR as metric_name,
        (SELECT COUNT(*)::NUMERIC FROM news_articles WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days') as metric_value,
        'count'::VARCHAR as metric_unit
    UNION ALL
    SELECT 
        'avg_summary_length'::VARCHAR as metric_name,
        (SELECT ROUND(AVG(CHAR_LENGTH(summary))) FROM news_articles WHERE summary IS NOT NULL) as metric_value,
        'characters'::VARCHAR as metric_unit
    UNION ALL
    SELECT 
        'articles_with_content'::VARCHAR as metric_name,
        (SELECT COUNT(*)::NUMERIC FROM news_articles WHERE summary IS NOT NULL AND summary != '') as metric_value,
        'count'::VARCHAR as metric_unit;
END;
$$;


ALTER FUNCTION public.get_advanced_stats() OWNER TO postgres;

--
-- TOC entry 299 (class 1255 OID 17749)
-- Name: get_source_stats(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_source_stats(days_back integer DEFAULT 7) RETURNS TABLE(source character varying, article_count bigint, last_article timestamp without time zone, avg_summary_length numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.source,
        COUNT(*) as article_count,
        MAX(a.timestamp) as last_article,
        ROUND(AVG(CHAR_LENGTH(COALESCE(a.summary, '')))) as avg_summary_length
    FROM news_articles a
    WHERE a.timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * days_back
    GROUP BY a.source
    ORDER BY article_count DESC;
END;
$$;


ALTER FUNCTION public.get_source_stats(days_back integer) OWNER TO postgres;

--
-- TOC entry 298 (class 1255 OID 17384)
-- Name: search_articles(text, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.search_articles(search_term text, limit_count integer DEFAULT 20) RETURNS TABLE(id integer, title character varying, summary text, source character varying, article_timestamp timestamp without time zone, rank real)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.title,
        a.summary,
        a.source,
        a.timestamp,
        ts_rank(a.search_vector, plainto_tsquery('romanian', search_term)) as rank
    FROM news_articles a
    WHERE a.search_vector @@ plainto_tsquery('romanian', search_term)
    ORDER BY rank DESC, a.timestamp DESC
    LIMIT limit_count;
END;
$$;


ALTER FUNCTION public.search_articles(search_term text, limit_count integer) OWNER TO postgres;

--
-- TOC entry 295 (class 1255 OID 17366)
-- Name: update_search_vector(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_search_vector() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('romanian', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('romanian', COALESCE(NEW.summary, '')), 'B') ||
        setweight(to_tsvector('romanian', COALESCE(NEW.content, '')), 'C');
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_search_vector() OWNER TO postgres;

--
-- TOC entry 297 (class 1255 OID 17370)
-- Name: update_timestamp(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_timestamp() OWNER TO postgres;

--
-- TOC entry 301 (class 1255 OID 18432)
-- Name: update_timestamp_insert_only(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_timestamp_insert_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                -- Always set created_at to current timestamp on INSERT
                IF TG_OP = 'INSERT' THEN
                    NEW.created_at = CURRENT_TIMESTAMP;
                    
                    -- Only set updated_at to current timestamp if it's NULL
                    -- This allows scrapers to explicitly set updated_at values
                    IF NEW.updated_at IS NULL THEN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                    END IF;
                END IF;
                
                RETURN NEW;
            END;
            $$;


ALTER FUNCTION public.update_timestamp_insert_only() OWNER TO postgres;

--
-- TOC entry 300 (class 1255 OID 18316)
-- Name: update_timestamp_smart(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_timestamp_smart() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                -- Only auto-update updated_at for INSERT operations
                -- For UPDATE operations, let the application control updated_at explicitly
                
                IF TG_OP = 'INSERT' THEN
                    -- For INSERT, set updated_at = created_at if not explicitly provided
                    IF NEW.updated_at IS NULL THEN
                        NEW.updated_at = NEW.created_at;
                    END IF;
                ELSIF TG_OP = 'UPDATE' THEN
                    -- For UPDATE, don't auto-modify updated_at
                    -- Let the application/scrapers control it explicitly
                    NULL; -- Do nothing
                END IF;
                
                RETURN NEW;
            END;
            $$;


ALTER FUNCTION public.update_timestamp_smart() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 229 (class 1259 OID 17335)
-- Name: app_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.app_settings (
    key character varying(100) NOT NULL,
    value text NOT NULL,
    description text,
    setting_type character varying(20) DEFAULT 'string'::character varying,
    is_encrypted boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.app_settings OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 17323)
-- Name: article_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.article_tags (
    article_id integer NOT NULL,
    tag character varying(100) NOT NULL,
    relevance_score numeric(3,2) DEFAULT 1.00,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.article_tags OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 17276)
-- Name: facebook_user_profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.facebook_user_profiles (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    bio text,
    connected_accounts text,
    profile_url character varying(1000),
    username character varying(100),
    location character varying(255),
    country character varying(10) DEFAULT 'RO'::character varying,
    age_range character varying(20),
    gender character varying(20),
    followers_count integer DEFAULT 0,
    friends_count integer DEFAULT 0,
    posts_count integer DEFAULT 0,
    avg_engagement_rate numeric(5,2) DEFAULT 0.00,
    last_post_date timestamp without time zone,
    interests text,
    topics_discussed text,
    is_verified boolean DEFAULT false,
    is_public boolean DEFAULT true,
    scraping_method character varying(50) DEFAULT 'automated'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_scraped_at timestamp without time zone,
    professional_title character varying(255),
    current_employer character varying(255),
    work_history text,
    education text,
    current_location character varying(255),
    origin_location character varying(255),
    relationship_status character varying(50),
    languages text,
    interests_detailed text,
    social_media_links text,
    religious_info text,
    church_position character varying(255),
    church_affiliation character varying(255),
    family_members text,
    life_events text,
    about_section text,
    favorite_quotes text,
    other_names text,
    contact_email character varying(255),
    contact_phone character varying(100),
    birthday character varying(50),
    political_views text
);


ALTER TABLE public.facebook_user_profiles OWNER TO postgres;

--
-- TOC entry 5085 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.username; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.username IS 'Facebook username extracted from profile';


--
-- TOC entry 5086 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.last_scraped_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.last_scraped_at IS 'Last time this profile was scraped';


--
-- TOC entry 5087 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.professional_title; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.professional_title IS 'Job title like Digital Creator, Protopsalt, etc.';


--
-- TOC entry 5088 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.current_employer; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.current_employer IS 'Current workplace or organization';


--
-- TOC entry 5089 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.work_history; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.work_history IS 'JSON array with work history';


--
-- TOC entry 5090 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.education; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.education IS 'JSON array with education details';


--
-- TOC entry 5091 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.current_location; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.current_location IS 'Current living location';


--
-- TOC entry 5092 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.origin_location; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.origin_location IS 'Origin or birth location';


--
-- TOC entry 5093 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.relationship_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.relationship_status IS 'Married, Single, etc.';


--
-- TOC entry 5094 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.languages; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.languages IS 'JSON array of spoken languages';


--
-- TOC entry 5095 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.interests_detailed; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.interests_detailed IS 'JSON array of detailed interests';


--
-- TOC entry 5096 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.social_media_links; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.social_media_links IS 'JSON object with external social links';


--
-- TOC entry 5097 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.religious_info; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.religious_info IS 'General religious information';


--
-- TOC entry 5098 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.church_position; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.church_position IS 'Position in church like Protopsalt, Diacon';


--
-- TOC entry 5099 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.church_affiliation; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.church_affiliation IS 'Affiliated church or cathedral';


--
-- TOC entry 5100 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.family_members; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.family_members IS 'JSON array cu informații despre membrii familiei';


--
-- TOC entry 5101 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.life_events; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.life_events IS 'JSON array cu evenimente importante din viață';


--
-- TOC entry 5102 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.about_section; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.about_section IS 'Secțiunea About/Despre din profilul Facebook';


--
-- TOC entry 5103 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.favorite_quotes; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.favorite_quotes IS 'Citate favorite';


--
-- TOC entry 5104 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.other_names; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.other_names IS 'Alte nume sau porecle';


--
-- TOC entry 5105 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.contact_email; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.contact_email IS 'Email de contact (public)';


--
-- TOC entry 5106 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.contact_phone; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.contact_phone IS 'Telefon de contact (public)';


--
-- TOC entry 5107 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.birthday; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.birthday IS 'Data nașterii (dacă e publică)';


--
-- TOC entry 5108 (class 0 OID 0)
-- Dependencies: 225
-- Name: COLUMN facebook_user_profiles.political_views; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.facebook_user_profiles.political_views IS 'Opinii politice';


--
-- TOC entry 224 (class 1259 OID 17275)
-- Name: facebook_user_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.facebook_user_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.facebook_user_profiles_id_seq OWNER TO postgres;

--
-- TOC entry 5109 (class 0 OID 0)
-- Dependencies: 224
-- Name: facebook_user_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.facebook_user_profiles_id_seq OWNED BY public.facebook_user_profiles.id;


--
-- TOC entry 223 (class 1259 OID 17246)
-- Name: news_articles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.news_articles (
    id integer NOT NULL,
    title character varying(500) NOT NULL,
    summary text NOT NULL,
    content text,
    link character varying(1000) NOT NULL,
    source character varying(100) NOT NULL,
    language character varying(10) DEFAULT 'ro'::character varying,
    published_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    content_hash character varying(64),
    search_vector tsvector
);


ALTER TABLE public.news_articles OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 17245)
-- Name: news_articles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.news_articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.news_articles_id_seq OWNER TO postgres;

--
-- TOC entry 5110 (class 0 OID 0)
-- Dependencies: 222
-- Name: news_articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.news_articles_id_seq OWNED BY public.news_articles.id;


--
-- TOC entry 221 (class 1259 OID 17204)
-- Name: news_sources; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.news_sources (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    base_url character varying(500) NOT NULL,
    description text,
    scraping_enabled boolean DEFAULT true,
    scraping_frequency integer DEFAULT 120,
    last_scraped_at timestamp without time zone,
    country character varying(10) DEFAULT 'RO'::character varying,
    language character varying(10) DEFAULT 'ro'::character varying,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.news_sources OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 17203)
-- Name: news_sources_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.news_sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.news_sources_id_seq OWNER TO postgres;

--
-- TOC entry 5111 (class 0 OID 0)
-- Dependencies: 220
-- Name: news_sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.news_sources_id_seq OWNED BY public.news_sources.id;


--
-- TOC entry 227 (class 1259 OID 17300)
-- Name: scraping_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.scraping_stats (
    id integer NOT NULL,
    session_id uuid DEFAULT public.uuid_generate_v4(),
    source_name character varying(100),
    articles_found integer DEFAULT 0,
    articles_new integer DEFAULT 0,
    articles_updated integer DEFAULT 0,
    articles_duplicates integer DEFAULT 0,
    profiles_found integer DEFAULT 0,
    profiles_new integer DEFAULT 0,
    duration_seconds integer,
    success boolean DEFAULT true,
    error_message text,
    scraper_version character varying(20) DEFAULT '1.0'::character varying,
    started_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamp without time zone
);


ALTER TABLE public.scraping_stats OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 17299)
-- Name: scraping_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.scraping_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.scraping_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5112 (class 0 OID 0)
-- Dependencies: 226
-- Name: scraping_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.scraping_stats_id_seq OWNED BY public.scraping_stats.id;


--
-- TOC entry 230 (class 1259 OID 17984)
-- Name: v_articles_complete; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_articles_complete AS
 SELECT id,
    title,
    summary,
    content,
    link,
    source,
    published_at,
    created_at,
    updated_at,
    COALESCE(ARRAY( SELECT at.tag
           FROM public.article_tags at
          WHERE (at.article_id = a.id)
          ORDER BY at.relevance_score DESC), ARRAY[]::character varying[]) AS tags
   FROM public.news_articles a;


ALTER VIEW public.v_articles_complete OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 17988)
-- Name: v_quick_stats; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_quick_stats AS
 SELECT ( SELECT count(*) AS count
           FROM public.news_articles) AS total_articles,
    ( SELECT count(*) AS count
           FROM public.facebook_user_profiles) AS total_profiles,
    ( SELECT count(*) AS count
           FROM public.news_articles
          WHERE (COALESCE(news_articles.published_at, news_articles.created_at) >= CURRENT_DATE)) AS articles_today,
    ( SELECT count(DISTINCT news_articles.source) AS count
           FROM public.news_articles) AS active_sources,
    ( SELECT count(*) AS count
           FROM public.news_articles
          WHERE (news_articles.published_at IS NOT NULL)) AS articles_with_publish_date;


ALTER VIEW public.v_quick_stats OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 17993)
-- Name: v_source_stats; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_source_stats AS
 SELECT source,
    count(*) AS article_count,
    count(
        CASE
            WHEN (COALESCE(published_at, created_at) >= CURRENT_DATE) THEN 1
            ELSE NULL::integer
        END) AS articles_today,
    count(
        CASE
            WHEN (COALESCE(published_at, created_at) >= (CURRENT_DATE - '7 days'::interval)) THEN 1
            ELSE NULL::integer
        END) AS articles_week,
    max(COALESCE(published_at, created_at)) AS last_published,
    round(avg(char_length(COALESCE(summary, ''::text)))) AS avg_summary_length,
    count(
        CASE
            WHEN ((summary IS NOT NULL) AND (summary <> ''::text)) THEN 1
            ELSE NULL::integer
        END) AS articles_with_summary,
    count(
        CASE
            WHEN (published_at IS NOT NULL) THEN 1
            ELSE NULL::integer
        END) AS articles_with_publish_date
   FROM public.news_articles
  GROUP BY source
  ORDER BY (count(*)) DESC;


ALTER VIEW public.v_source_stats OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 17998)
-- Name: v_temporal_stats; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_temporal_stats AS
 SELECT date(COALESCE(published_at, created_at)) AS article_date,
    count(*) AS article_count,
    count(DISTINCT source) AS sources_active,
    round(avg(char_length(COALESCE(summary, ''::text)))) AS avg_summary_length,
    count(
        CASE
            WHEN (published_at IS NOT NULL) THEN 1
            ELSE NULL::integer
        END) AS articles_with_publish_date
   FROM public.news_articles
  WHERE (COALESCE(published_at, created_at) >= (CURRENT_DATE - '30 days'::interval))
  GROUP BY (date(COALESCE(published_at, created_at)))
  ORDER BY (date(COALESCE(published_at, created_at))) DESC;


ALTER VIEW public.v_temporal_stats OWNER TO postgres;

--
-- TOC entry 4856 (class 2604 OID 17279)
-- Name: facebook_user_profiles id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.facebook_user_profiles ALTER COLUMN id SET DEFAULT nextval('public.facebook_user_profiles_id_seq'::regclass);


--
-- TOC entry 4852 (class 2604 OID 17249)
-- Name: news_articles id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_articles ALTER COLUMN id SET DEFAULT nextval('public.news_articles_id_seq'::regclass);


--
-- TOC entry 4844 (class 2604 OID 17207)
-- Name: news_sources id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_sources ALTER COLUMN id SET DEFAULT nextval('public.news_sources_id_seq'::regclass);


--
-- TOC entry 4867 (class 2604 OID 17303)
-- Name: scraping_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scraping_stats ALTER COLUMN id SET DEFAULT nextval('public.scraping_stats_id_seq'::regclass);


--
-- TOC entry 4920 (class 2606 OID 17345)
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);


--
-- TOC entry 4916 (class 2606 OID 17329)
-- Name: article_tags article_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.article_tags
    ADD CONSTRAINT article_tags_pkey PRIMARY KEY (article_id, tag);


--
-- TOC entry 4901 (class 2606 OID 17296)
-- Name: facebook_user_profiles facebook_user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.facebook_user_profiles
    ADD CONSTRAINT facebook_user_profiles_pkey PRIMARY KEY (id);


--
-- TOC entry 4903 (class 2606 OID 17298)
-- Name: facebook_user_profiles facebook_user_profiles_profile_url_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.facebook_user_profiles
    ADD CONSTRAINT facebook_user_profiles_profile_url_key UNIQUE (profile_url);


--
-- TOC entry 4895 (class 2606 OID 17264)
-- Name: news_articles news_articles_content_hash_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_articles
    ADD CONSTRAINT news_articles_content_hash_key UNIQUE (content_hash);


--
-- TOC entry 4897 (class 2606 OID 17262)
-- Name: news_articles news_articles_link_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_articles
    ADD CONSTRAINT news_articles_link_key UNIQUE (link);


--
-- TOC entry 4899 (class 2606 OID 17260)
-- Name: news_articles news_articles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_articles
    ADD CONSTRAINT news_articles_pkey PRIMARY KEY (id);


--
-- TOC entry 4885 (class 2606 OID 17221)
-- Name: news_sources news_sources_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_sources
    ADD CONSTRAINT news_sources_name_key UNIQUE (name);


--
-- TOC entry 4887 (class 2606 OID 17219)
-- Name: news_sources news_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.news_sources
    ADD CONSTRAINT news_sources_pkey PRIMARY KEY (id);


--
-- TOC entry 4914 (class 2606 OID 17317)
-- Name: scraping_stats scraping_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scraping_stats
    ADD CONSTRAINT scraping_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4917 (class 1259 OID 17365)
-- Name: idx_article_tags_relevance; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_article_tags_relevance ON public.article_tags USING btree (relevance_score DESC);


--
-- TOC entry 4918 (class 1259 OID 17364)
-- Name: idx_article_tags_tag; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_article_tags_tag ON public.article_tags USING btree (tag);


--
-- TOC entry 4904 (class 1259 OID 20158)
-- Name: idx_facebook_profiles_church; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_church ON public.facebook_user_profiles USING btree (church_position);


--
-- TOC entry 4905 (class 1259 OID 20160)
-- Name: idx_facebook_profiles_last_scraped; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_last_scraped ON public.facebook_user_profiles USING btree (last_scraped_at);


--
-- TOC entry 4906 (class 1259 OID 17358)
-- Name: idx_facebook_profiles_location; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_location ON public.facebook_user_profiles USING btree (location);


--
-- TOC entry 4907 (class 1259 OID 17357)
-- Name: idx_facebook_profiles_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_name ON public.facebook_user_profiles USING btree (name);


--
-- TOC entry 4908 (class 1259 OID 20157)
-- Name: idx_facebook_profiles_profession; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_profession ON public.facebook_user_profiles USING btree (professional_title);


--
-- TOC entry 4909 (class 1259 OID 17359)
-- Name: idx_facebook_profiles_updated; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_updated ON public.facebook_user_profiles USING btree (updated_at DESC);


--
-- TOC entry 4910 (class 1259 OID 20159)
-- Name: idx_facebook_profiles_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_facebook_profiles_username ON public.facebook_user_profiles USING btree (username);


--
-- TOC entry 4888 (class 1259 OID 17350)
-- Name: idx_news_articles_content_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_news_articles_content_hash ON public.news_articles USING btree (content_hash);


--
-- TOC entry 4889 (class 1259 OID 18004)
-- Name: idx_news_articles_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_news_articles_created_at ON public.news_articles USING btree (created_at DESC);


--
-- TOC entry 4890 (class 1259 OID 17349)
-- Name: idx_news_articles_published_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_news_articles_published_at ON public.news_articles USING btree (published_at DESC);


--
-- TOC entry 4891 (class 1259 OID 17356)
-- Name: idx_news_articles_search; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_news_articles_search ON public.news_articles USING gin (search_vector);


--
-- TOC entry 4892 (class 1259 OID 17346)
-- Name: idx_news_articles_source; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_news_articles_source ON public.news_articles USING btree (source);


--
-- TOC entry 4893 (class 1259 OID 18003)
-- Name: idx_news_source_published_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_news_source_published_date ON public.news_articles USING btree (source, published_at DESC);


--
-- TOC entry 4911 (class 1259 OID 17363)
-- Name: idx_scraping_stats_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_scraping_stats_date ON public.scraping_stats USING btree (started_at DESC);


--
-- TOC entry 4912 (class 1259 OID 17362)
-- Name: idx_scraping_stats_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_scraping_stats_session ON public.scraping_stats USING btree (session_id);


--
-- TOC entry 4923 (class 2620 OID 17369)
-- Name: news_articles trigger_generate_content_hash; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_generate_content_hash BEFORE INSERT OR UPDATE ON public.news_articles FOR EACH ROW EXECUTE FUNCTION public.generate_content_hash();


--
-- TOC entry 4924 (class 2620 OID 18433)
-- Name: news_articles trigger_insert_timestamp_news_articles; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_insert_timestamp_news_articles BEFORE INSERT ON public.news_articles FOR EACH ROW EXECUTE FUNCTION public.update_timestamp_insert_only();


--
-- TOC entry 4925 (class 2620 OID 17367)
-- Name: news_articles trigger_update_search_vector; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_update_search_vector BEFORE INSERT OR UPDATE ON public.news_articles FOR EACH ROW EXECUTE FUNCTION public.update_search_vector();


--
-- TOC entry 4926 (class 2620 OID 17372)
-- Name: facebook_user_profiles trigger_update_timestamp_facebook_profiles; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_update_timestamp_facebook_profiles BEFORE UPDATE ON public.facebook_user_profiles FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- TOC entry 4922 (class 2620 OID 17373)
-- Name: news_sources trigger_update_timestamp_news_sources; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_update_timestamp_news_sources BEFORE UPDATE ON public.news_sources FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- TOC entry 4921 (class 2606 OID 17330)
-- Name: article_tags article_tags_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.article_tags
    ADD CONSTRAINT article_tags_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.news_articles(id) ON DELETE CASCADE;


-- Completed on 2025-07-11 01:59:54

--
-- PostgreSQL database dump complete
--

