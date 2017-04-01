using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Xml.Linq;
using MyAnimeListSharp.Auth;
using MyAnimeListSharp.Core;
using MyAnimeListSharp.Enums;
using MyAnimeListSharp.Facade;
using MyAnimeListSharp.Facade.Async;

namespace PlexMALSync
{
  internal class Program
  {
    private static ICredentialContext _malCredentials;
    private static string _processedAnimeCacheFile;
    private static bool _processing;
    private static string _malUsername;

    private static void Main(string[] args)
    {
      try
      {
        // Assign variables
        _malUsername = args[0];
        var malPassword = args[1];
        var plexHost = args[2];
        var plexToken = args[3];
        var plexSection = args[4];

        // Create _MALCredentials cache
        _malCredentials = new CredentialContext
        {
          UserName = _malUsername,
          Password = malPassword
        };

        // Link cache
        _processedAnimeCacheFile = $"AnimeProcessed_{_malUsername}.cache";
        _processing = true;

        var sections = new List<string>();

        if (plexSection.Contains(","))
          sections = plexSection.Split(',').ToList();
        else
          sections.Add(plexSection);

        // Process Plex sections  
        ProcesPlexSections(plexHost, plexToken, sections);
        while (_processing)
          Thread.Sleep(2500);
      }
      catch (Exception e)
      {
        Console.WriteLine($"Invalid arguments received: {e}");
      }
    }

    private static async void ProcesPlexSections(string server, string token, List<string> sections)
    {
      try
      {
        var animeTitles = new List<string>();
        foreach (var section in sections)
        {
          string url = $"http://{server}/library/sections/{section}/all?X-Plex-Token={token}";
          string filename = $"PlexLibrary_{_malUsername} [{section}].xml";

          var wc = new WebClient();
          wc.DownloadFile(url, filename);

          var xDcoument = XDocument.Load(filename);

          var titles = from doc in xDcoument.Descendants("Directory") let attribute = doc.Attribute("title") where attribute != null select attribute.Value;
          foreach (var title in titles)
            animeTitles.Add(title.Trim());
        }

        // Process them with MyAnimeList
        if (animeTitles.Any())
        {
          var animeProcessedCache = ReadAllProcessed();
          foreach (var title in animeTitles)
            if (!animeProcessedCache.Contains(title))
              await ProcessAnime(title);
        }

        _processing = false;
      }
      catch (Exception e)
      {
        Console.WriteLine(e);
        _processing = false;
      }
    }

    private static async Task ProcessAnime(string animeInputName)
    {
      Console.WriteLine($"Processing anime: {animeInputName}");

      var animeValues = new AnimeValues
      {
        AnimeStatus = AnimeStatus.PlanToWatch,
        Comments = ""
      };

      var asyncAnimeSearcher = new AnimeSearchMethodsAsync(_malCredentials);
      var response = await asyncAnimeSearcher.SearchDeserializedAsync(animeInputName);

      if (response == null || response.Entries.Count == 0)
      {
        Console.WriteLine($"No MAL results found for: {animeInputName}");
        return;
      }

      var match = false;
      var responseTitles = new List<string>();
      foreach (var result in response.Entries)
      {
        var animeTitle = result.Title;
        var animeTitleEnglish = result.English;
        var animeSynonyms = result.Synonyms;
        var animeSynonymsList = new List<string>();
        if (animeSynonyms.Contains(";"))
          animeSynonymsList = animeSynonyms.Split(';').ToList();

        var animeId = result.Id;
        responseTitles.Add(result.Title);

        // Original or English title matching
        if (animeTitle.ToLowerInvariant() == animeInputName.ToLowerInvariant() || animeTitleEnglish.ToLowerInvariant() == animeInputName.ToLowerInvariant())
        {
          Console.WriteLine($"Adding {animeTitle} | {animeTitleEnglish} to list..");
          AddAnime(animeId, animeValues);
          match = true;
          break;
        }

        // Single synonym matching
        if (animeSynonyms.ToLowerInvariant() == animeInputName.ToLowerInvariant() && animeSynonymsList.Count == 0)
        {
          Console.WriteLine($"Adding {animeSynonyms} [synonym matched to list..");
          AddAnime(animeId, animeValues);
          match = true;
          break;
        }

        // Multiple synonyms matching
        if (animeSynonymsList.Count > 0)
        {
          foreach (var synonym in animeSynonymsList)
          {
            var synonymClean = synonym.Trim();
            if (synonymClean.ToLowerInvariant() == animeInputName.ToLowerInvariant())
            {
              Console.WriteLine($"Adding {synonymClean} | {animeTitleEnglish} to list [synonyms matched");
              AddAnime(animeId, animeValues);
              match = true;
              break;
            }

            responseTitles.Add(synonymClean);
          }
        }
      }

      if (match)
      {
        WriteProcessed(animeInputName);
      }
      else
      {
        Console.WriteLine($"No MAL title match found in results for: {animeInputName}");
      }

    }

    private static void AddAnime(int animeId, AnimeValues animeValues)
    {
      var methods = new AnimeListMethods(_malCredentials);
      var responseText = methods.AddAnime(animeId, animeValues);

      if (responseText.Contains("already in the list"))
        Console.WriteLine("Anime already added to list");
      else
        Console.WriteLine(responseText);
    }

    private static HashSet<string> ReadAllProcessed()
    {
      var processed = new HashSet<string>();

      if (File.Exists(_processedAnimeCacheFile))
      {
        string line;
        var sr = new StreamReader(_processedAnimeCacheFile);
        while ((line = sr.ReadLine()) != null)
          processed.Add(line);

        sr.Close();
      }
      return processed;
    }

    private static void WriteProcessed(string animeTitle)
    {
      var sw = new StreamWriter(_processedAnimeCacheFile, true);
      sw.WriteLine(animeTitle);
      sw.Close();
    }
  }
}
