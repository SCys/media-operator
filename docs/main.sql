create index on media_history (id_user);

create table if not exists media_history
(
    id                 text        not null,
    ts_create          timestamptz not null default now(),
    ts_update          timestamptz not null default now(),
    removed            bool        not null default false,
    info               jsonb       not null default '{}'::jsonb,

    id_user            text,

    -- input
    input_size         int         not null,
    input_video_codec  text,
    input_audio_codec  text,
    input_width        int,
    input_height       int,

    -- output
    output_size        int         not null,
    output_video_codec text,
    output_audio_codec text,
    output_width       int,
    output_height      int,

    -- task info
    cost               bigint      not null, -- unit ms

    primary key (id)
);

create index on media_history (id_user, ts_create);
