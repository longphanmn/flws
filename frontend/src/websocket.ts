import type { ControlMessage, DeltaStateMessage, EntityState, HelloMessage, StateMessage } from './types'

export type ConnStatus = 'connecting' | 'open' | 'closed'

interface Handlers {
  onHello?: (msg: HelloMessage) => void
  onState?: (msg: StateMessage) => void
  onControl?: (msg: { type: 'control'; paused: boolean; speed: number; tick: number }) => void
  onStatus?: (status: ConnStatus) => void
  /** server rejected a control message for lack of a valid passkey */
  onAuthError?: () => void
}

/** WebSocket client with exponential-backoff auto-reconnect and delta state reconstruction. */
export class WorldSocket {
  private ws: WebSocket | null = null
  private attempts = 0
  private disposed = false
  private timer: ReturnType<typeof setTimeout> | undefined

  // Phase 1 AJ: Entity state map for reconstructing deltas into complete StateMessages
  private entitiesMap: Map<number, EntityState> = new Map()
  private entitiesList: EntityState[] = []
  private entitiesDirty = true
  private lastFullState: StateMessage | null = null

  constructor(
    private url: string,
    private handlers: Handlers,
  ) {}

  connect(): void {
    if (this.disposed) return
    this.handlers.onStatus?.('connecting')
    const ws = new WebSocket(this.url)
    this.ws = ws
    ws.onopen = () => {
      this.attempts = 0
      this.handlers.onStatus?.('open')
    }
    ws.onmessage = (ev) => this.handle(ev.data)
    ws.onerror = () => ws.close()
    ws.onclose = () => {
      this.handlers.onStatus?.('closed')
      this.ws = null
      if (!this.disposed) {
        const delay = Math.min(5000, 400 * 2 ** this.attempts++)
        this.timer = setTimeout(() => this.connect(), delay)
      }
    }
  }

  private handle(raw: string): void {
    try {
      const msg = JSON.parse(raw)
      if (msg.type === 'state') {
        const fullMsg = msg as StateMessage
        this.lastFullState = fullMsg
        this.entitiesMap.clear()
        if (fullMsg.entities) {
          for (const e of fullMsg.entities) {
            this.entitiesMap.set(e.id, e)
          }
          this.entitiesList = [...fullMsg.entities]
        } else {
          this.entitiesList = []
        }
        this.entitiesDirty = false
        this.handlers.onState?.(fullMsg)
      } else if (msg.type === 'delta_state') {
        const delta = msg as DeltaStateMessage
        if (!this.lastFullState) {
          return
        }
        // Apply removals
        if (delta.remove_ids && delta.remove_ids.length > 0) {
          for (const id of delta.remove_ids) {
            this.entitiesMap.delete(id)
          }
          this.entitiesDirty = true
        }
        // Apply upserts
        if (delta.upsert_entities && delta.upsert_entities.length > 0) {
          for (const e of delta.upsert_entities) {
            const existing = this.entitiesMap.get(e.id)
            if (existing) {
              Object.assign(existing, e)
            } else {
              this.entitiesMap.set(e.id, e)
              this.entitiesDirty = true
            }
          }
        }
        if (this.entitiesDirty) {
          this.entitiesList = Array.from(this.entitiesMap.values())
          this.entitiesDirty = false
        }
        // Reconstruct complete StateMessage
        const reconstructed: StateMessage = {
          ...this.lastFullState,
          type: 'state',
          tick: delta.tick,
          seed: delta.seed ?? this.lastFullState.seed,
          population: delta.population,
          creatures_alive: delta.creatures_alive,
          creatures_dead: delta.creatures_dead,
          dead_by_cause: delta.dead_by_cause,
          infected_count: delta.infected_count,
          time_of_day: delta.time_of_day,
          day: delta.day,
          season: delta.season,
          relations: delta.relations && delta.relations.length > 0 ? delta.relations : (this.lastFullState?.relations ?? []),
          clans: delta.clans && Object.keys(delta.clans).length > 0 ? { ...(this.lastFullState?.clans ?? {}), ...delta.clans } : (this.lastFullState?.clans ?? {}),

          signals: delta.signals,
          fires: delta.fires,
          age: delta.age,
          age_tick: delta.age_tick,
          age_day: delta.age_day,
          age_total_days: delta.age_total_days,
          rivers: delta.rivers ?? this.lastFullState?.rivers ?? [],
          bridges: delta.bridges ?? this.lastFullState?.bridges ?? [],
          dams: delta.dams ?? this.lastFullState?.dams ?? [],
          entities: this.entitiesList,
          paused: delta.paused ?? this.lastFullState.paused,
          analytics: (delta as any).analytics ?? (this.lastFullState as any)?.analytics,
          safeguard_active: delta.safeguard_active ?? this.lastFullState?.safeguard_active ?? false,
          softcap_active: delta.softcap_active ?? this.lastFullState?.softcap_active ?? false,
        }
        this.lastFullState = reconstructed
        this.handlers.onState?.(reconstructed)
      } else if (msg.type === 'hello') {
        this.handlers.onHello?.(msg as HelloMessage)
      } else if (msg.type === 'control') {
        this.handlers.onControl?.(msg)
      } else if (msg.type === 'auth_error') {
        this.handlers.onAuthError?.()
      }
    } catch {
      // ignore malformed frames
    }
  }

  send(msg: ControlMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  dispose(): void {
    this.disposed = true
    if (this.timer) clearTimeout(this.timer)
    this.ws?.close()
  }
}

