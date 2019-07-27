# changes from v2 to v3, backend wise

 - config file's RATELIMITS moved formats, it doesnt follow path stuff anymore,
    which is more robust.
   - the bad part is that it doesn't use url paths anymore, but instead
     uses the blueprint import path as a selector
