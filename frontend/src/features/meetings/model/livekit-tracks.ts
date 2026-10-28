import {
  type LocalTrackPublication,
  type RemoteParticipant,
  type RemoteTrack,
  type RemoteTrackPublication,
  type Room,
  Track,
} from "livekit-client";

import type { VideoKind } from "../domain/call-session";
import { playAudio } from "./livekit-media";
import { SOURCE_OF } from "./livekit-people";

/*
 * Дорожки звонка по элементам страницы: видео подписывается только для плиток на сцене (meetings §1.3) и
 * отпускается, когда плитка ушла; звук — от всех.
 */

// Плитка ушла со сцены не насовсем, если вернулась за это время: подписка не дёргается при перерисовке.
const UNSUBSCRIBE_AFTER_MS = 1_500;

const kindOf = (source: Track.Source): VideoKind => (source === Track.Source.ScreenShare ? "screen" : "camera");

export class TrackStage {
  private readonly elements = new Map<string, HTMLVideoElement>();
  private readonly releases = new Map<string, number>();

  constructor(
    private readonly room: Room,
    private readonly self: string,
  ) {}

  /** Видео человека в элементе плитки; null — плитка ушла со сцены. */
  attach(identity: string, kind: VideoKind, element: HTMLVideoElement | null) {
    const key = `${identity}/${kind}`;
    const own = identity === this.self ? this.room.localParticipant : undefined;
    const publication = (own ?? this.room.remoteParticipants.get(identity))?.getTrackPublication(SOURCE_OF[kind]);
    const remote = own ? undefined : (publication as RemoteTrackPublication | undefined);
    window.clearTimeout(this.releases.get(key));
    if (!element) {
      this.elements.delete(key);
      if (remote)
        this.releases.set(
          key,
          window.setTimeout(() => remote.setSubscribed(false), UNSUBSCRIBE_AFTER_MS),
        );
      return;
    }
    this.elements.set(key, element);
    remote?.setSubscribed(true);
    if (publication?.track && !publication.track.attachedElements.includes(element)) publication.track.attach(element);
  }

  /** Звук участника — подписка сразу, как он вошёл. */
  subscribeAudio(participant: RemoteParticipant) {
    for (const publication of participant.audioTrackPublications.values()) publication.setSubscribed(true);
  }

  /** Новая дорожка: звук — всегда, видео — если его плитка уже на сцене. */
  want(publication: RemoteTrackPublication, participant: RemoteParticipant) {
    const key = `${participant.identity}/${kindOf(publication.source)}`;
    if (publication.kind === Track.Kind.Audio || this.elements.has(key)) publication.setSubscribed(true);
  }

  /** Подписанная дорожка: звук — играть, видео — в элемент своей плитки. */
  show(track: RemoteTrack, identity: string) {
    if (track.kind === Track.Kind.Audio) return playAudio(track);
    const element = this.elements.get(`${identity}/${kindOf(track.source)}`);
    if (element) track.attach(element);
  }

  /** Своя опубликованная дорожка — в элемент своей плитки. */
  showLocal(publication: LocalTrackPublication) {
    const element = this.elements.get(`${this.self}/${kindOf(publication.source)}`);
    if (element && publication.track) publication.track.attach(element);
  }
}
