def topics(database):
    return database.rows(
        "SELECT t.id,t.name,COUNT(nt.note_id) note_count FROM topics t "
        "JOIN note_topics nt ON nt.topic_id=t.id GROUP BY t.id ORDER BY t.name")
