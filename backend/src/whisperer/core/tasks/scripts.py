"""Lua scripts of the task streams: each step that must be atomic is one script, one round trip.

A worker changes a message only while the message is still its own: between a check and
a change in separate commands another worker could claim it, and the change would take
the message back or settle someone else's run (draft lesson). Acknowledgement is the one
exception — a run that succeeded settles the message whoever holds it now.
"""

from typing import Final

# KEYS[1] — поток; ARGV[1] — предел длины, ARGV[2] — тело. Полный поток отказывает (nil),
# а не обрезается: обрезка по длине молча выбросила бы самые старые невыполненные задачи.
ENQUEUE: Final = """
if redis.call('XLEN', KEYS[1]) >= tonumber(ARGV[1]) then
  return false
end
return redis.call('XADD', KEYS[1], '*', 'data', ARGV[2])
"""

# KEYS[1] — поток; ARGV[1] — группа, ARGV[2] — потребитель, ARGV[3…] — id сообщений.
# XCLAIM с JUSTID обнуляет простой и не увеличивает счётчик выдач. Ответ — id, оставшиеся нашими.
RENEW: Final = """
local kept = {}
for i = 3, #ARGV do
  local entry = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[i], ARGV[i], 1)
  if entry[1] and entry[1][2] == ARGV[2] then
    redis.call('XCLAIM', KEYS[1], ARGV[1], ARGV[2], 0, ARGV[i], 'JUSTID')
    kept[#kept + 1] = ARGV[i]
  end
end
return kept
"""

# KEYS[1] — поток; ARGV[1] — группа, ARGV[2] — id. Выполненное удаляется из потока сразу:
# длина потока — это глубина очереди, а тела выполненных задач в нём не копятся.
ACKNOWLEDGE: Final = """
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
return redis.call('XDEL', KEYS[1], ARGV[2])
"""

# KEYS[1] — поток; ARGV[1] — группа, ARGV[2] — потребитель, ARGV[3] — id, ARGV[4] — простой в мс.
# Сообщение остаётся в списке ожидания с простоем «аренда минус пауза»: восстановление
# любого воркера выдаст его снова, когда пауза пройдёт. Место в воркере на паузу не занято.
RETRY_LATER: Final = """
local entry = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[3], ARGV[3], 1)
if not (entry[1] and entry[1][2] == ARGV[2]) then
  return 0
end
redis.call('XCLAIM', KEYS[1], ARGV[1], ARGV[2], 0, ARGV[3], 'IDLE', ARGV[4], 'JUSTID')
return 1
"""

# KEYS[1] — поток, KEYS[2] — dead letter; ARGV[1] — группа, ARGV[2] — потребитель, ARGV[3] — id,
# ARGV[4] — запись, ARGV[5] — предел записей, ARGV[6] — граница возраста (id потока).
# Запись и снятие сообщения — одна операция: ни потери следа, ни повторной записи.
DEAD_LETTER: Final = """
local entry = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[3], ARGV[3], 1)
if not (entry[1] and entry[1][2] == ARGV[2]) then
  return 0
end
redis.call('XADD', KEYS[2], 'MAXLEN', '~', ARGV[5], '*', 'entry', ARGV[4])
redis.call('XTRIM', KEYS[2], 'MINID', '~', ARGV[6])
redis.call('XACK', KEYS[1], ARGV[1], ARGV[3])
redis.call('XDEL', KEYS[1], ARGV[3])
return 1
"""

# KEYS — пары «поток, dead letter» каждой очереди. На пару — длина потока, id первой записи
# (самая старая невыполненная задача), длина dead letter и id его последней записи.
QUEUE_GAUGES: Final = """
local result = {}
for i = 1, #KEYS, 2 do
  local oldest = redis.call('XRANGE', KEYS[i], '-', '+', 'COUNT', 1)
  local newest = redis.call('XREVRANGE', KEYS[i + 1], '+', '-', 'COUNT', 1)
  result[#result + 1] = redis.call('XLEN', KEYS[i])
  result[#result + 1] = oldest[1] and oldest[1][1] or false
  result[#result + 1] = redis.call('XLEN', KEYS[i + 1])
  result[#result + 1] = newest[1] and newest[1][1] or false
end
return result
"""
